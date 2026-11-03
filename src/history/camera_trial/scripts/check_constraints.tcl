# Runs after init_design, before expensive implementation phases.
set critical_count [get_msg_config -count -severity {CRITICAL WARNING}]
if {$critical_count > 0} {
    error "Constraint/linking critical warnings remain ($critical_count); inspect impl_1/runme.log."
}
puts "CONSTRAINT PREFLIGHT PASSED: no linking/constraint critical warnings."
