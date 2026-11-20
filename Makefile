PORT ?= auto
MPREMOTE = uv run mpremote connect $(PORT)
FIRMWARE ?= ESP32_GENERIC_S3-SPIRAM_OCT-20260824-v1.29.0.bin

upload:
	$(MPREMOTE) fs cp main.py config.py ssd1306.py : + fs cp -r app www : + reset

flash:
	uv run esptool --chip esp32s3 erase-flash
	uv run esptool --chip esp32s3 --baud 921600 write-flash 0 $(FIRMWARE)

sim:
	uv run --with pillow python tools/simulator.py

repl:
	$(MPREMOTE)

ls:
	$(MPREMOTE) fs tree

reset:
	$(MPREMOTE) reset

.PHONY: upload flash sim repl ls reset
