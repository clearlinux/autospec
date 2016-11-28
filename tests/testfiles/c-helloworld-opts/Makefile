DESTDIR ?=
PREFIX ?= /usr/local

helloworld:
	gcc main.c -o helloworld

clean:
	rm helloworld

install: helloworld
	install -m 0755 -d $(DESTDIR)$(PREFIX)/bin
	install -m 0755 helloworld $(DESTDIR)$(PREFIX)/bin
