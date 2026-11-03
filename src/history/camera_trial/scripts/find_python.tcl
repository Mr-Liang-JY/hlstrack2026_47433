set lab_root [file dirname [file dirname [file normalize [info script]]]]
set candidates [list [file normalize [file join $lab_root .. .. .venv Scripts python.exe]] python python3]
if {[info exists ::env(HDMI_PYTHON)]} {set candidates [linsert $candidates 0 $::env(HDMI_PYTHON)]}
set python_cmd {}
foreach candidate $candidates {
    if {[file isfile $candidate]} {set python_cmd $candidate; break}
    if {[llength [auto_execok $candidate]]} {set python_cmd [lindex [auto_execok $candidate] 0]; break}
}
if {$python_cmd eq {}} {error "Python 3 not found; set HDMI_PYTHON."}
