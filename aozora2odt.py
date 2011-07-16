#!/usr/bin/python
# -*- coding: utf-8 -*-
from odf.opendocument import OpenDocumentText, load
from odf.text import P, Ruby, RubyBase, RubyText, Span
from odf.style import Style, RubyProperties, TextProperties
import optparse
import sys
import os

class DocumentGenerator:
    def __init__( self, template=None ):
        if not template:
            self.doc = OpenDocumentText()
        else:
            self.doc = load( template )
        self.cur_par = None
        self._create_styles()

    def _create_styles( self ):
        #Creating new ruby style
        self.ruby_style_name = "RubyMy"
        my_ruby_style = Style( name=self.ruby_style_name, family="ruby" )
        my_ruby_style.addElement( 
            RubyProperties( rubyalign = "center", 
                            rubyposition = "above" ) )
        self.doc.automaticstyles.addElement( my_ruby_style )
        
        #Create dotted style
        self.dot_style_name = "DottedMy"
        my_dotted_style = Style( name = self.dot_style_name, 
                                 family="text" )
        my_dotted_style.addElement(
            TextProperties( textemphasize="dot above" ) )
        self.doc.automaticstyles.addElement( my_dotted_style )

    def _ensure_cur_par( self ):
        if self.cur_par == None:
            self.cur_par = P()

    def add_text( self, text ):
        self._ensure_cur_par()
        self.cur_par.addText( text )

    def add_text_dotted( self, text ):
        self._ensure_cur_par()
        self.cur_par.addElement(
            Span( stylename=self.dot_style_name,
                  text = text ) )
            
    def new_paragraph( self ):
        if self.cur_par:
            self.doc.text.addElement( self.cur_par )
            self.cur_par = None
        else:
            self.doc.text.addElement( P() )

    def new_page( self ):
        #TODO
        self.new_paragraph()

    def add_rubied_text( self, text, ruby ):
        self._ensure_cur_par()
        ruby_elt = Ruby( stylename= self.ruby_style_name )
        ruby_elt.addElement( RubyBase( text = text ) )
        ruby_elt.addElement( RubyText( text = ruby ) )
        self.cur_par.addElement( ruby_elt )

    def end( self ):
        if self.cur_par:
            self.doc.text.addElement( self.cur_par )
            self.cur_par = None

    def save( self, fname ):
        if self.cur_par:
            self.end()
        self.doc.save( fname, not fname.endswith( ".odt" ) )



def parse_aozora_line( line, gen ):
    """line is an unicode string
    """
    parsed = []
    state = "normal" #Other: "ruby", "ruby_text", "dotted_begin", "dotted"

    ruby = []
    ruby_text = []
    command_desc = []

    def process_command():
        #process current dotted description
        #Extract the text that contains dots
        #  「オマエ［＃「オマエ」に傍点］、本当についてねーよ［＃「本当についてねーよ」に傍点］」
        command = u"".join( command_desc )
        if command == u"改ページ":
            #New page
            gen.new_page()
            return
        if command.startswith(u"「") and command.endswith( u"」に傍点" ): #Add emph dots
            dotted_text = command_desc[1:-4]
            dotted_len = len( dotted_text )
            parsed_part = parsed[ (-dotted_len) : ]
            if parsed_part != dotted_text:
                print "#Warning! Dotted text (%d chars):"%len(dotted_text), u"".join( dotted_text ).encode( "utf-8" )
                print "#         But parsed contains:", u"".join( map( unicode, parsed_part) ).encode( "utf-8" )
                print "#         Ignored"
                return
            else:#OK. Remove dotted part from the usual text and add as emphasised
                del parsed[ (-dotted_len) : ]
                parsed.append( ("dotted", u"".join(dotted_text) ) )
        else:
            print "Unknown command:", u"".join(command_desc).encode( "utf-8" )
        
    for char in line:
        if state == "normal":
            if char == u"｜": #begin of the ruby
                state = "ruby"
                ruby = []
                ruby_text = []
                continue
            elif char == u"［": #begin dotted description ［＃
                state = "dotted_begin"
                continue
            else:
                #normal char
                parsed.append( char )
                continue
        elif state == "ruby":
            if char == u"《": #end of a ruby, begin ruby text
                state = "ruby_text"
                continue
            else:#usual ruby char
                ruby.append( char )
                continue
        elif state == "ruby_text":
            if char == u"》": #end of the ruby text
                parsed.append( ("ruby", u"".join(ruby), u"".join(ruby_text) ) )
                state = "normal"
                continue
            else: #normal ruby text
                ruby_text.append( char )
        elif state == "dotted_begin":
            if char == u"＃": #continue dotted description
                state = "dotted"
                command_desc = []
                continue
            else:
                #No, that was not a dotted desc - return as an usual character to the text
                parsed.extend( u"［＃" )
                state = "normal"
        elif state == "dotted":
            #Reading dotted description
            if char == u"］":
                process_command()
                state = "normal"
                continue
            else:#continue reading dotted description
                command_desc.append( char )
                

    def group_text():
        """Group text items"""
        cur_text = []
        for item in parsed:
            if isinstance( item, unicode ):
                cur_text.append( item )
            else:
                if cur_text:
                    yield ("text", u"".join( cur_text ) )
                    cur_text = []
                yield item
        if cur_text:
            yield ("text", u"".join( cur_text ) )

    #Finally, generate the document
    cur_text = []
    for item in group_text():
        if item[0] == "text":
            #usual characters
            gen.add_text( item[1] )
        elif item[0] == "ruby":
            gen.add_rubied_text( item[1], item[2] )
        elif item[0] == "dotted":
            gen.add_text_dotted( item[1] ) 

    gen.new_paragraph()

def parse_aozora_text( input_file, encoding, gen, max_lines = None ):
    """parse aozora file with rubym using the specified generator to produce the text"""
    lineno = 0
    while True:
        line = input_file.readline()
        if not line: break

        lineno += 1
        parse_aozora_line( line.decode( encoding ), gen )
        if lineno % 100 == 0:
            print "Parsed %d lines"%lineno
            sys.stdout.flush()
        if max_lines != None and lineno > max_lines:
            break
    gen.end()


if __name__ == '__main__':
    parser = optparse.OptionParser()
    parser.add_option( "-T", "--template", dest="template", help="Template to use for export (empty *.odt file)" )
    parser.add_option( "-C", "--codepage", dest="codepage", help="Encoding of the source file (utf-8, sjis)", default="utf-8" )
    parser.add_option( "-o", "--output", dest="output", help="Output file" )
    options, args = parser.parse_args()
    
    if len(args) == 0:
        sys.stderr.write( "No input files\n" )
        sys.exit( -1 )
    if len(args) > 1 and options.output:
        sys.stderr.write( "Several input files specified, but there is only one output. Don't use -o in this case.")
        sys.exit( -1 )
    
    
    for input_file in args:
        print "Processing ", input_file
        #Determine output file
        if options.output:
            output = options.output
        else:
            base_name = os.path.splitext( os.path.split( input_file )[1] )[0]
            output = base_name+".odt"
        #process the file
        gen = DocumentGenerator( options.template )
        ifile = open( input_file, "r" )
        parse_aozora_text( ifile, options.codepage, gen )
        ifile.close()
        gen.save( output )
    
    sys.exit( 0 )
