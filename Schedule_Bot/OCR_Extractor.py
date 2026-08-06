# importing nessary modules
import pytesseract
from PIL import Image
from pdf2image import convert_from_path as pdf_path

# creating a function to extract text from image
def image_extractor(image):
    # opening image
    img = Image.open(image)
    # extracting text from image using pytesseract
    text = pytesseract.image_to_string(img)
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

# calling function
if __name__ == "__main__":
    raw = image_extractor("/Users/enoch/Desktop/Connectivity_A/Schedule_Bot/Data/Schedule.png")
    print(raw)
    print("---LENGTH---", len(raw))
