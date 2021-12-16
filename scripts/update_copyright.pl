#!/usr/bin/perl -w
# Licensed under the EUPL v1.2
# © 2021 bicobus <bicobus@keemail.me>
use utf8;
use strict;
use warnings;
use POSIX qw(strftime);

use Path::Tiny;

my $YEAR = strftime "%Y", localtime;

sub copy_regex
{
    s/^(\s*\#[*\s]*(?:©|Copyright)) (\d{4}-)\d{4} ([Bb]icobus)/$1 $2$YEAR $3/gm;
    s/^(\s*\#[*\s]*(?:©|Copyright)) (\d{4}) ([Bb]icobus)/$1 $2-$YEAR $3/gm
}

sub update_copyright
{
    my $file = path(shift);
    $file->edit_utf8(\&copy_regex);
}

sub main
{
    my $iter = path("../qmm/")->iterator( { recurse => 1 } );
    while (my $path = $iter->()) {
        if ($path =~ qr/qmm\/(?!ui_)[\w\/]+(?<!_rc)\.py\z/) {
            update_copyright($path);
        }
    }
}

main();
exit 0