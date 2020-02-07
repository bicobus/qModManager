RCC := $(shell command -v pyrcc5 2>/dev/null)
UIC := $(shell command -v pyuic5 2>/dev/null)
UIC_FLAGS=--from-imports
RDIR=resources
LDIR=qmm
PUI=$(LDIR)/icons_rc.py\
	$(LDIR)/ui_settings.py\
	$(LDIR)/ui_mainwindow.py\
	$(LDIR)/ui_qprogress.ui\
	$(LDIR)/ui_about.py

ifndef RCC
    $(error "pyrcc5 not found in PATH, make not run within virtualenv?")
endif
ifndef UIC
    $(error "pyuic5 not found in PATH, make not run within virtualenv?")
endif

.PHONY: all clean qt

all: qt

qt: $(PUI)

$(LDIR)/ui_%.py: $(RDIR)/ui_%.ui
	$(UIC) $(UIC_FLAGS) -o $@ $<

$(LDIR)/%_rc.py: $(RDIR)/%.qrc
	$(RCC) -o $@ $<

clean: 
	$(RM) $(PUI)
	-find . -name '__pycache__' -prune -exec rm -rf "{}" \;
	-find . -name '*.pyc' -delete

