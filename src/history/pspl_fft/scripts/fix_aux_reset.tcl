# Repair the auxiliary-reset polarity in the supplied Day 5/Day 6 project.
# Run from Vivado Tcl Console with the intended project open.
# This script regenerates hardware. It never edits a .hwh to hide a mismatch.

if {[llength [get_projects -quiet]] != 1} {
    error "Open the Day 5 or Day 6 project before sourcing this script."
}
set fix_project [current_project]
set fix_name [get_property NAME $fix_project]
if {$fix_name ni {day5_pspl_project day6_pspl_fft_project}} {
    error "This patch is only for day5_pspl_project or day6_pspl_fft_project."
}
set fix_project_dir [file normalize [get_property DIRECTORY $fix_project]]
set fix_lab_root [file dirname [file dirname $fix_project_dir]]
set fix_builder [file join $fix_lab_root scripts build_bitstream.tcl]
if {![file isfile $fix_builder]} {
    error "Build script not found: $fix_builder. Check the project folder structure."
}
if {[llength [get_designs -quiet]] > 0} {
    close_design
}
set fix_bds [get_files -quiet */system.bd]
if {[llength $fix_bds] != 1} {error "Expected exactly one system.bd: $fix_bds"}
open_bd_design [lindex $fix_bds 0]
set fix_reset [get_bd_cells -quiet proc_sys_reset_0]
set fix_zero [get_bd_cells -quiet const_zero]
if {[llength $fix_reset] != 1 || [llength $fix_zero] != 1} {
    error "Expected proc_sys_reset_0 and const_zero in the supplied design."
}
if {[get_property CONFIG.CONST_VAL $fix_zero] != 0} {
    error "const_zero is not zero. Review the design before changing reset polarity."
}
set fix_aux_net [get_bd_nets -quiet -of_objects [get_bd_pins proc_sys_reset_0/aux_reset_in]]
set fix_zero_net [get_bd_nets -quiet -of_objects [get_bd_pins const_zero/dout]]
if {[llength $fix_aux_net] != 1 || $fix_aux_net ne $fix_zero_net} {
    error "aux_reset_in is not tied to const_zero. This patch does not apply unchanged."
}

# Also patch the original project creator so a fresh project keeps the fix.
set fix_creator [file join $fix_lab_root scripts create_project.tcl]
if {[file isfile $fix_creator]} {
    set fix_stream [open $fix_creator r]
    set fix_source [read $fix_stream]
    close $fix_stream
    if {![regexp {CONFIG\.C_AUX_RESET_HIGH\s+\{?1\}?} $fix_source]} {
        set fix_anchor {set_property CONFIG.C_EXT_RESET_HIGH {0} [get_bd_cells proc_sys_reset_0]}
        if {[string first $fix_anchor $fix_source] < 0} {
            error "Creator differs from the supplied script. Add C_AUX_RESET_HIGH=1 to it before retrying."
        }
        set fix_line {set_property CONFIG.C_AUX_RESET_HIGH {1} [get_bd_cells proc_sys_reset_0]}
        set fix_backup "${fix_creator}.before_aux_fix_[clock seconds]"
        file copy $fix_creator $fix_backup
        set fix_source [string map [list $fix_anchor "$fix_anchor\n$fix_line"] $fix_source]
        set fix_stream [open $fix_creator w]
        puts -nonewline $fix_stream $fix_source
        close $fix_stream
        puts "Patched project creator. Backup: $fix_backup"
    }
}

puts "Before: C_AUX_RESET_HIGH=[get_property CONFIG.C_AUX_RESET_HIGH $fix_reset]"
set_property CONFIG.C_AUX_RESET_HIGH {1} $fix_reset
if {[get_property CONFIG.C_AUX_RESET_HIGH $fix_reset] != 1} {
    error "Failed to select active-high auxiliary reset."
}
validate_bd_design
save_bd_design
generate_target all $fix_bds
puts "AUX RESET FIX APPLIED: aux_reset_in=0 is now inactive."

# Reset synthesis and its dependent implementation, then use the normal builder.
reset_run synth_1
source $fix_builder

if {$fix_name eq "day5_pspl_project"} {
    set fix_stem day5_pspl
} else {
    set fix_stem day6_pspl_fft
}
set fix_hwh [file join $fix_lab_root out ${fix_stem}.hwh]
if {![file isfile $fix_hwh]} {error "New HWH file missing: $fix_hwh"}
set fix_stream [open $fix_hwh r]
set fix_hwh_text [read $fix_stream]
close $fix_stream
if {![regexp {NAME="C_AUX_RESET_HIGH"\s+VALUE="1"} $fix_hwh_text]} {
    error "Exported HWH does not contain C_AUX_RESET_HIGH=1. Do not upload this output pair."
}
puts "RESET FIX AND BUILD FINISHED"
puts "Upload BOTH new files: ${fix_stem}.bit and ${fix_stem}.hwh from [file join $fix_lab_root out]"
