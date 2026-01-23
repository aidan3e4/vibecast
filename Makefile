.PHONY: capture viewer help

help:
	@echo "Available commands:"
	@echo "  make viewer   - Start the session viewer web UI"
	@echo "  make capture  - Run camera capture (pass args with ARGS='...')"
	@echo ""
	@echo "Examples:"
	@echo "  make viewer"
	@echo "  make capture ARGS='--once'"
	@echo "  make capture ARGS='-f 30 -v N S E W'"

viewer:
	python3 -m viewer.session_viewer

capture:
	python3 -m clients.camera_capture $(ARGS)
