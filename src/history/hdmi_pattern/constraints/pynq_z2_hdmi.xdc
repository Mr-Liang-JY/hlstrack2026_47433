# PYNQ-Z2 HDMI OUT, connector J11. Source: Xilinx/PYNQ v3.0.1 base.xdc.
# https://raw.githubusercontent.com/Xilinx/PYNQ/v3.0.1/boards/Pynq-Z2/base/vivado/constraints/base.xdc
# Upstream pin assignment data: Copyright (C) 2022 Xilinx, Inc, BSD-3-Clause.
set_property -dict {PACKAGE_PIN L16 IOSTANDARD TMDS_33} [get_ports hdmi_clk_p]
set_property -dict {PACKAGE_PIN L17 IOSTANDARD TMDS_33} [get_ports hdmi_clk_n]
set_property -dict {PACKAGE_PIN K17 IOSTANDARD TMDS_33} [get_ports {hdmi_data_p[0]}]
set_property -dict {PACKAGE_PIN K18 IOSTANDARD TMDS_33} [get_ports {hdmi_data_n[0]}]
set_property -dict {PACKAGE_PIN K19 IOSTANDARD TMDS_33} [get_ports {hdmi_data_p[1]}]
set_property -dict {PACKAGE_PIN J19 IOSTANDARD TMDS_33} [get_ports {hdmi_data_n[1]}]
set_property -dict {PACKAGE_PIN J18 IOSTANDARD TMDS_33} [get_ports {hdmi_data_p[2]}]
set_property -dict {PACKAGE_PIN H18 IOSTANDARD TMDS_33} [get_ports {hdmi_data_n[2]}]
set_property -dict {PACKAGE_PIN R19 IOSTANDARD LVCMOS33} [get_ports hdmi_hpd_n]
set_property -dict {PACKAGE_PIN D19 IOSTANDARD LVCMOS33} [get_ports button_reset]
set_property -dict {PACKAGE_PIN R14 IOSTANDARD LVCMOS33} [get_ports {leds[0]}]
set_property -dict {PACKAGE_PIN P14 IOSTANDARD LVCMOS33} [get_ports {leds[1]}]
set_property -dict {PACKAGE_PIN N16 IOSTANDARD LVCMOS33} [get_ports {leds[2]}]
set_property -dict {PACKAGE_PIN M14 IOSTANDARD LVCMOS33} [get_ports {leds[3]}]
# Asynchronous inputs terminate only at reset assertion or the first synchronizer.
# The clocks are related MMCM outputs: do NOT cut pixel-to-serializer timing.
set_false_path -from [get_ports button_reset]
set_false_path -from [get_ports hdmi_hpd_n]
# These two slow, independent debug bits are intentionally sampled by two FFs.
# Only the D pin of the FIRST FF is asynchronous. The first-to-second FF path
# remains timed at 100 MHz. Do not cut the entire video/serializer clock pair.
set_false_path -to [get_pins -hier -regexp {.*\/(alive_sync|rstn_sync)_reg\[0\]/D}]
