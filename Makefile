RCC=pyrcc5
UIC=pyuic5 --from-imports
RDIR=qmm/resources
LDIR=qmm
QRC=$(RDIR)/icons.qrc
#DEPS=$(RDIR)/ui_customlist.ui $(RDIR)/ui_detailedview.ui $(QRC)
PUI=$(LDIR)/ui_customlist.py $(LDIR)/ui_detailedview.py $(LDIR)/icons_rc.py\
	$(LDIR)/ui_mainwindow.py

$(LDIR)/ui_%.py: $(RDIR)/ui_%.ui
	$(UIC) -o $@ $<

$(LDIR)/%_rc.py: $(RDIR)/%.qrc
	$(RCC) -o $@ $<

compile: $(PUI)

.PHONEY: clean
clean: 
	$(RM) $(PUI)
