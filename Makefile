UIC=pyuic5
RDIR=qmm/resources
LDIR=qmm
DEPS=$(RDIR)/ui_customlist.ui
PUI=$(LDIR)/ui_customlist.py

$(LDIR)/%.py: $(RDIR)/%.ui
	$(UIC) -o $@ $<

compile: $(PUI)

.PHONEY: clean
clean: 
	$(RM) $(PUI)
