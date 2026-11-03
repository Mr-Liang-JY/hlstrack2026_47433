set lab_root [file dirname [file dirname [file normalize [info script]]]]
set candidates [list [file normalize [file join $lab_root .. .. .venv Scripts python.exe]] python python3]
if {[info exists ::env(HDMI_PYTHON)]} {set candidates [linsert $candidates 0 $::env(HDMI_PYTHON)]}
set python_cmd {}
foreach candidate $candidates {
    if {[file isfile $candidate]} {set python_cmd $candidate; break}
    if {[llength [auto_execok $candidate]]} {set python_cmd [lindex [auto_execok $candidate] 0]; break}
}
if {$python_cmd eq {}} {error "Python 3 not found. Set HDMI_PYTHON or run scripts/package.py manually."}
# Vivado sets PYTHONHOME/PYTHONPATH for its bundled Python 3.8. Ignore those
# variables when launching a different Python, otherwise its stdlib can mismatch.
puts [exec $python_cmd -I [file join $lab_root scripts package.py]]
