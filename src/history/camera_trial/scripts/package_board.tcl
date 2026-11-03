source [file join [file dirname [file normalize [info script]]] find_python.tcl]
puts [exec $python_cmd -I [file join $lab_root scripts package.py]]
puts [exec $python_cmd -I [file join $lab_root scripts verify_delivery.py]]
