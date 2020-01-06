RCC=pyrcc5
UIC=pyuic5 --from-imports
RDIR=resources
LDIR=qmm
#DEPS=$(RDIR)/ui_customlist.ui $(RDIR)/ui_detailedview.ui $(QRC)
PUI=$(LDIR)/icons_rc.py\
	$(LDIR)/ui_settings.py\
	$(LDIR)/ui_mainwindow.py\
	$(LDIR)/ui_about.py

.PHONY: clean qt

$(LDIR)/ui_%.py: $(RDIR)/ui_%.ui
	$(UIC) -o $@ $<

$(LDIR)/%_rc.py: $(RDIR)/%.qrc
	$(RCC) -o $@ $<

qt: $(PUI)

clean: 
	$(RM) $(PUI)
	-find . -name '__pycache__' -prune -exec rm -rf "{}" \;
	-find . -name '*.pyc' -delete

