set lab_root [file dirname [file dirname [file normalize [info script]]]]
if {[llength [get_projects -quiet]]} {error "Save and close the current project first."}
set lab_sim_dir [file join $lab_root validation sim_project]
if {[file exists [file join $lab_sim_dir day9_sim.xpr]]} {
    open_project [file join $lab_sim_dir day9_sim.xpr]
} else {
    create_project day9_sim $lab_sim_dir -part xc7z020clg400-1
    add_files [list [file join $lab_root rtl sobel3x3_core.v] [file join $lab_root rtl sobel_frame_axis.v]]
    add_files -fileset sim_1 [file join $lab_root sim tb_sobel_frame_axis.sv]
    add_files -fileset sim_1 [file join $lab_root sim vectors.txt]
    set_property file_type {Data Files} [get_files */vectors.txt]
    set_property top sobel_frame_axis [get_filesets sources_1]
    set_property top tb_sobel_frame_axis [get_filesets sim_1]
    set_property xsim.simulate.runtime all [get_filesets sim_1]
}
launch_simulation
close_sim
puts "DAY9 SIMULATION COMMAND FINISHED; inspect xsim log for the explicit PASS line."
