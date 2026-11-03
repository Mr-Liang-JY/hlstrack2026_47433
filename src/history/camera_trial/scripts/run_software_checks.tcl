source [file join [file dirname [file normalize [info script]]] find_python.tcl]
set result [exec $python_cmd -I [file join $lab_root sim test_sccb_protocol.py]]
set f [open [file join $lab_root out test_sccb_protocol.log] w]
fconfigure $f -encoding utf-8
puts $f $result;close $f
puts $result
if {![string match {*PASS SCCB*} $result]} {error "SCCB protocol test failed."}
