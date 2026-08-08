# importing nessary modules
import pytesseract
from PIL import Image
from pdf2image import convert_from_path as pdf_path
from Schedule_Bot.schedule_pharaser import time_extractor
from Schedule_Bot.schedule_pharaser import day_splitter

# creating a function to extract text from image
def image_extractor(image):
    # opening image
    img = Image.open(image)
    # converting image to grayscale ("L" mode, which stands for Luminance) yea luminance = intensity of light
    img = img.convert("L")
    # upscaling the image by a factor of 3 to improve OCR accuracy or upscale = 300%
    img = img.resize((img.width * 3, img.height * 3))
    # maximizing the contrast of the image to make the text stand out more against the background
    img = ImageOps.autocontrast(img)
    # extracting text from image using pytesseract and config="--psm 6" sets the Page Segmentation Mode to assume a single uniform block of text.
    text = pytesseract.image_to_string(img, config="--psm 6")
    # return extracted text
    return text


# creating a function to extract text from pdf
def pdf_extractor(pdf):
    # opening pdf pages
    pages = pdf_path(pdf)
    full_text = ""
    # iterating through pages
    for page in pages:
        full_text += image_extractor(page) + "\n"
    return full_text

# TODO: Fix this currently returns []
# calling function
if __name__ == "__main__":
    from PIL import Image, ImageOps

    img = Image.open("data/Schedule.png")
    img = img.convert("L")                          # grayscale
    img = img.resize((img.width * 3, img.height * 3))  # upscale 3x
    img = ImageOps.autocontrast(img)                 # boost contrast

    text = pytesseract.image_to_string(img, config="--psm 6")
    print(len(text))
    print(text)