# Only for this project's deliberate RTL edits; resets THIS project's runs.
set script_dir [file dirname [file normalize [info script]]]
if {![llength [get_projects -quiet]]} {source [file join $script_dir create_project.tcl]}
if {[get_property NAME [current_project]] ne "day9_shm_pspl_project"} {error "Wrong project"}
if {[llength [get_designs -quiet]]} {close_design}
open_bd_design [lindex [get_files -quiet */system.bd] 0]
# Ports/parameters are unchanged; regenerate targets and resynthesize the RTL.
# update_module_reference is unnecessary for an arithmetic-only edit.
update_compile_order -fileset sources_1
validate_bd_design
save_bd_design
generate_target all [get_files -quiet */system.bd]
foreach run [get_runs -quiet *sobel_frame*_synth_1] {reset_run $run}
reset_run synth_1
source [file join $script_dir build_bitstream.tcl]
