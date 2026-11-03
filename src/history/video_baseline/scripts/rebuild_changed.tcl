set lab_root [file dirname [file dirname [file normalize [info script]]]]
source [file join $lab_root scripts create_project.tcl]
open_bd_design [get_files */system.bd]
# Port contracts are unchanged; reset OOC runs to re-read the referenced RTL.
update_compile_order -fileset sources_1
validate_bd_design
save_bd_design
generate_target all [get_files */system.bd]
reset_run synth_1
foreach name {system_video_display_0_0_synth_1 system_sobel_frame_0_0_synth_1} {
    reset_run $name
}
source [file join $lab_root scripts build_bitstream.tcl]
