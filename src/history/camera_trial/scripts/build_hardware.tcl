# Use only after the RTL simulation logs have passed; build_all.tcl runs both stages.
set script_dir [file dirname [file normalize [info script]]]
if {[catch {
    source [file join $script_dir create_project.tcl]
    source [file join $script_dir build_bitstream.tcl]
} message options]} {
    puts stderr "HDMI HARDWARE BUILD FAILED: $message"
    puts stderr [dict get $options -errorinfo]
    exit 1
}
