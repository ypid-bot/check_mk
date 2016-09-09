#################################################################################
#
# NAME: 	windows_updates.ps1
#
# COMMENT:  Script to check for windows updates with Check_MK
#
#           Checks:
#           - how many critical and optional updates are available
#           - whether the system is waiting for reboot after installed updates
#
#           Features:
#           - properly handles NRPE's 1024b limitation in return packet
#           - configurable return states for pending reboot and optional updates
#           - performance data in return packet shows titles of available critical updates
#           - caches updates in file to reduce network traffic, also dramatically increases script execution speed
#
# IMPORTANT: 	Please make absolutely sure that your Powershell ExecutionPolicy is set to Remotesigned.
#				Also note that there are two versions of powershell on a 64bit OS! Depending on the architecture
#				of your NSClient++ version you have to choose the right one:
#
#				64bit NSClient++ (installed under C:\Program Files ):
#				%SystemRoot%\SysWOW64\WindowsPowerShell\v1.0\powershell.exe "Set-ExecutionPolicy RemoteSigned"
#
#				32bit NSClient++ (installed under C:\Program Files (x86) ):
#				%SystemRoot%\syswow64\WindowsPowerShell\v1.0\powershell.exe "Set-ExecutionPolicy RemoteSigned"
#
#
# CHANGELOG:
# 2.0.0 2016-09-08 - Switched to Check_MK <<<windows_updates>>> format to allow to use this script as drop in replacement for windows_updates.vbs
# 1.45 2016-08-05 - corrected some typos, added newline after each critical update
# 1.44 2016-04-05 - performance data added
# 1.42 2015-07-20 - strip unwanted characters from returnString
# 1.41 2015-04-24 - removed wuauclt /detectnow if updates available
# 1.4  2015-01-14 - configurable return state for pending reboot
# 1.3  2013-01-04 - configurable return state for optional updates
# 1.2  2011-08-11 - cache updates, periodically update cache file
# 1.1  2011-05-11 - hidden updates only -> state OK
#				  - call wuauctl.exe to show available updates to user
# 1.0  2011-05-10 - initial version
#
#################################################################################
# Copyright (C) 2011-2015 Christian Kaufmann, ck@tupel7.de
# Copyright (C) 2016 Robin Schneider <robin.schneider@hamcos.de>
# Copyright (C) 2016 hamcos IT Service GmbH http://www.hamcos.de
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, see <http://www.gnu.org/licenses>.
#################################################################################

$htReplace = New-Object hashtable
foreach ($letter in (Write-Output ä ae ö oe ü ue Ä Ae Ö Oe Ü Ue ß ss)) {
    $foreach.MoveNext() | Out-Null
    $htReplace.$letter = $foreach.Current
}
$pattern = "[$(-join $htReplace.Keys)]"

$returnStateOK = 0
$returnStateWarning = 1
$returnStateCritical = 2
$returnStateUnknown = 3
$returnStatePendingReboot = $returnStateWarning
$returnStateOptionalUpdates = $returnStateWarning

$logFile = "check_windows_update.log"

function LogLine(	[String]$logFile = $(Throw 'LogLine:$logFile unspecified'),
					[String]$row = $(Throw 'LogLine:$row unspecified')) {
	$logDateTime = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
	Add-Content -Encoding UTF8 $logFile ($logDateTime + " - " + $row)
}

$criticalTitles = "";
$countCritical = 0;
$countOptional = 0;
$countHidden = 0;
$rebootRequired = 0

if (Test-Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired"){
	if (Test-Path $logFile) {
		Remove-Item $logFile | Out-Null
	}
	$rebootRequired = 1
}

foreach ($update in $updates) {
	if ($update.IsHidden) {
		$countHidden++
	}
	elseif ($update.AutoSelectOnWebSites) {
		# $criticalTitles += $update.Title + " `n"
		$countCritical++
	} else {
		$countOptional++
	}
}

Write-Host "<<<windows_updates>>>"
Write-Host "$rebootRequired $countCritical $countOptional"
# Not implemented:
Write-Host ""
Write-Host ""
Write-Host "no_key"
