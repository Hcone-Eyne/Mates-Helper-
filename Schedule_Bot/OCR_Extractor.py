# importing nessary modules
import pytesseract
from PIL import Image
from pdf2image import convert_from_path as pdf_path
from Schedule_Bot.schedule_pharaser import time_extractor
from Schedule_Bot.schedule_pharaser import day_splitter
from Schedule_Bot.schedule_pharaser import Days
from datetime import datetime
import pandas as pd

# adding date and time!
def datatime_fetcher(prompt):
    while True:
        # getting time string from user
        time_string = input(prompt).strip()
        try:
            # check if the format is correct or not, if not raise value error
            parsed_time = datetime.strptime(time_string, "%I:%M %p")
            return parsed_time.strftime("%I:%M %p") # return true answer 
        except ValueError: #
            print("[Fox]: Invalid time format. Please enter the time in the format 'HH:MM AM/PM' (e.g., 09:30 AM).")


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

# creating a function to quality check
def quality_checker(image, expected_days = 5 ):
    # extract the text and check if the text is trustworthy or not
    days_found = sum (1 for day in Days if day.lower() in image.lower())
    # check the fetched condition
    if days_found < expected_days or len(image) < 300:
        return False # didnt meet = reject
    return True # meet condition = accept

def schedule_text_extractor(image_path):
    # gettning image text using path and image_extractor function
    raw_data = image_extractor(image_path)
    # quality check
    if quality_checker(raw_data):
        return raw_data # if true it return raw data
    else:
        print("[Fox]: Couldn't Read - Image Quality Is Too Low.")
        print("[Fox]: Please Try Again With A Clearer Image Or Use Enter Schedule Manually. ")
        return Manual_Input() # if false it return manual input function

# Manual Input Function the name itself tells about the function!
def Manual_Input():
    # the schedule data
    data = { "day": [], "subject": [], "time_start": [], "time_end": [], "books_needed": []}
    print("[Fox]: Please Enter Your Schedule Manually.")
    print("[Fox]: Enter 'done' when you are finished entering your schedule.")
    try:
        while True:
            # getting day from user
            day = input("[Fox]: Enter Day of Schedule: ").strip()
            # if done is input break!
            if day.lower() == "done":
                break

            # if user input is not in Days list, ask again
            if day not in Days:
                print("[Fox]: Invalid day. Please enter a valid day.")
                continue

            # inputs for the subjects
            subject = input("[Fox]: Enter Subject: ").strip()
            time_start = datatime_fetcher("[Fox]: Enter Start Time (HH:MM): ")
            time_end = datatime_fetcher("[Fox]: Enter End Time (HH:MM)")
            books = input("[Fox]: Books needed (optional, press enter to skip):").strip()

            # adding the input data to the list!
            data["day"].append(day)
            data["subject"].append(subject)
            data["time_start"].append(time_start)
            data["time_end"].append(time_end)
            data["books_needed"].append(books)

            print(f"Added: {day} — {subject}\n")
    # the breaker
    except KeyboardInterrupt:
        print("[Fox]: Entry cancelled — saving what you've entered so far.") # notifies the user!

    # return the made up value
    return pd.DataFrame(data)    





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