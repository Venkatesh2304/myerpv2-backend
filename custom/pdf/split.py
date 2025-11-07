import glob
from io import BytesIO
import os
import PyPDF2
import re 
import shutil
from tqdm import tqdm 

def _create_directory_for_file(fname) : 
    directory = os.path.dirname(fname)
    if directory : os.makedirs( directory , exist_ok = True )

def group_pdfs_into_folders(src_fldr,get_folder_name) :
    src_fldr = src_fldr.rstrip("/") 
    files = glob.glob(f"{src_fldr}/*.pdf")
    for file in tqdm(files) : 
        with open(file, 'rb') as f :
             pdf_reader = PyPDF2.PdfFileReader(f)
             fldr = get_folder_name(pdf_reader)
        os.makedirs(fldr,exist_ok=True)
        shutil.copyfile(file,os.path.join(fldr,os.path.basename(file)))

class LastPageFindMethods :
    # "Page : ([0-9]+) of ([0-9]+)"
    def page_footer_1(curr_page,page_text) :  
        """Method to find the last page using Page : 3 of 5"""
        page_find = re.findall(r"Page : ([0-9]+) of ([0-9]+)",page_text)[0]
        _curr_page , tot_page = int(page_find[0]) , int(page_find[1])
        if curr_page != _curr_page : raise Exception("parse method 1 not applicable")  ## assertion check 
        return curr_page == tot_page 

    def page_footer_2(curr_page,page_text) :     
        """Method to find the last page using 3 of Page : 5"""
        page_find = re.findall(r"([0-9]+) of Page:",page_text)
        l = len(str(curr_page))
        if str(curr_page) == page_find[0][-l:] : 
            tot_page = int(page_find[0][ : -l ])
        else : 
           print( pdf_file_path , page_num )
           print( page_text )
           raise Exception("parse method 2 not applicable") 
        return curr_page == tot_page 

    # Pattern to identify 
    def create_pattern_method(pattern) : 
      """Create a pattern matcher method , which checks for a pattern to detect last page"""
      def pattern_match(curr_page,page_text) : 
          page_find = re.findall(pattern,page_text)
          return len(page_find) != 0 
      return pattern_match

def split_using_last_page(fname,find_last_page_method,get_pdf_name,temp_buffer = False):
    files = {}
    with open(fname, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        total_pages = len(pdf_reader.pages)
        curr_page = 0   
        first_page_text = ""
        for page_num in range(total_pages):
            page = pdf_reader.pages[page_num]
            page_text = page.extract_text()
            curr_page += 1 
            is_last_page = find_last_page_method(curr_page,page_text)  #To make it work for only one bill 
            
            if curr_page == 1 : 
               pdf_writer = PyPDF2.PdfWriter() 
               first_page_text = page_text
           
            pdf_writer.add_page(page)
            
            if is_last_page :
               curr_page = 0 
               if first_page_text == "" : 
                  print("empty page")
                  continue   
               try :
                 fname = get_pdf_name(first_page_text)
                 print( fname )
               except Exception as e : 
                 print("Debug Info :",page_text)
                 raise e 
                
               if temp_buffer : 
                    output_buffer = BytesIO()
                    pdf_writer.write(output_buffer)
                    files[fname] =  output_buffer
               else : 
                    _create_directory_for_file(fname)
                    with open(fname, 'wb') as output_file:
                        pdf_writer.write(output_file)
    return files