.DELETE_ON_ERROR:
POMERGE ?= 0
RCC := $(shell command -v pyrcc5 2>/dev/null)
UIC := $(shell command -v pyuic5 2>/dev/null)
UICFLAGS = --from-imports
LDIR = qmm
PUI=${LDIR}/icons_rc.py\
	${LDIR}/ui_settings.py\
	${LDIR}/ui_mainwindow.py\
	${LDIR}/ui_qprogress.py\
	${LDIR}/ui_about.py

POFILES       = $(wildcard locales/*/LC_MESSAGES/qmm.po)
TRANSLATIONS  = $(patsubst %.po,%.mo,$(POFILES))

vpath %.ui resources
vpath %.qrc resources

#ifndef RCC
#$(error "pyrcc5 not found in PATH, make not run within virtualenv?")
#endif
#ifndef UIC
#$(error "pyuic5 not found in PATH, make not run within virtualenv?")
#endif

.PHONY: all clean ui

all: ui .build/i18n

.PHONY: .maint/pipupdate
.maint/pipupdate:
	pipenv update --outdated && pipenv update
	pipenv update --dev --outdated && pipenv update --dev
	pipenv lock -r > requirements.txt

.PHONY: .build/req
.build/req:
	pip install -r requirements.txt
	pip install pyinstaller

.PHONY: .build/i18n .build/i18n-update
.build/i18n: $(TRANSLATIONS)
.build/i18n-update: $(POFILES)

.PHONY: .build/pot
.build/pot:
	xgettext --default-domain=qmm --language=Python\
		--add-comments=TRANSLATORS: --add-comments=Translators:\
		-o locales/qmm.pot qmm/*.py

locales/%/LC_MESSAGES/qmm.mo: locales/%/LC_MESSAGES/qmm.po
	msgfmt $< --output-file $@

locales/%/LC_MESSAGES/qmm.po: locales/qmm.pot
ifeq ($(POMERGE), 1)
	msgmerge --update $@ $<
endif

ui: $(PUI)

$(LDIR)/ui_%.py: ui_%.ui
	$(UIC) $(UICFLAGS) -o $@ $<
# importing _ shouldn't be needed as gettext gets initialized at application
# start
#	sed -i -r -e '/^# -\*- coding: [a-z0-9-]+ -\*-/{N;s/$$/from .lang import _/}'
# $ might be interpreted as a variable, doubling to escape
# replace all Qt _translate with gettext's _
	sed -i -r -e 's/_translate\(".*?", /_(/'\
		-e 's/, None.*/))/'\
		-e 's/( +)(_translate = .*\.translate)/\1#\2/' $@

$(LDIR)/%_rc.py: %.qrc
	$(RCC) -o $@ $<

clean: 
	$(RM) $(PUI)
	-find . -name '__pycache__' -prune -exec rm -rf "{}" \;
	-find . -name '*.pyc' -delete

