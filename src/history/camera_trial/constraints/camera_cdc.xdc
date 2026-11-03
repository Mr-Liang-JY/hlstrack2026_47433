# Apply after module-reference checkpoints are linked (implementation only).
# Only first synchronizer stages are asynchronous; second stages remain timed.
set_false_path -to [get_pins -hier -regexp {.*\/cdc_meta_reg(\[[0-9]+\])?/D}]
# Registered Gray buses: constrain bit flight time below the 48MHz source period.
# A sequential startpoint is the register C pin (Q would segment timing paths).
set_max_delay -datapath_only 20.000 -from [get_pins -hier -regexp {.*\/src_gray_reg(\[[0-9]+\])?/C}] -to [get_pins -hier -regexp {.*\/gray_meta_reg(\[[0-9]+\])?/D}]
set_false_path -hold -to [get_pins -hier -regexp {.*\/gray_meta_reg(\[[0-9]+\])?/D}]
# These are ONLY the async-assert pins of the three-stage reset synchronizers.
# Deassertion is re-timed through pipe[0:2]; downstream reset/data paths stay timed.
set_false_path -to [get_pins -hier -regexp {.*\/(cr|pr|br|vr|rs)\/pipe_reg\[[0-2]\]/PRE}]
