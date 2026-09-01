# importing nessary modules
import pytesseract
from PIL import Image
from pdf2image import convert_from_path as pdf_path
from datetime import datetime

# ahh too much library!
import pandas as pd
from PIL import Image, ImageOps
from pdf2image import convert_from_path as pdf_path
from img2table.document import Image as TableImage # i used TableImage to prevent the error ( u have used that image variable agian that's why)
from img2table.ocr import TesseractOCR

# AgAIN TOo MUch LibraRY!
from Schedule_Bot.schedule_pharaser import Days

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
    # maximizing the contrast of the
    #  image to make the text stand out more against the background
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
def quality_checker(image, expected_days = 2 ):
    # extract the text and check if the text is trustworthy or not
    days_found = sum (1 for day in Days if day.lower() in image.lower())
    # check the fetched condition
    if days_found < expected_days or len(image) < 300:
        return False # didnt meet = reject
    return True # meet condition = accept

# this is used to check the givem image and decide to accept or reject!
def schedule_text_extractor(image_path):
    # gettning image text using path and image_extractor function
    raw_data = image_extractor(image_path)
    print("--- RAW OCR OUTPUT ---")
    print(raw_data)
    print("--- LENGTH:", len(raw_data), "---")
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
            time_start = datatime_fetcher("[Fox]: Enter Start Time (HH:MM) - ")
            time_end = datatime_fetcher("[Fox]: Enter End Time (HH:MM) - ")
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

# adding a extract table function to detect image grid by grid to fetch ine information
def extract_table(image_path):
    # setting up the tesseract lang eng so while fetching it won't fail
    ocr = TesseractOCR(lang = "eng")
    # location of the image
    doc = TableImage(image_path)
    # table is used to extract info from the table
    tables = doc.extract_tables(ocr = ocr)

    # defining the table df
    data_remover = tables[0].df
    # removing the lunch / break column (yes uisng the positions)
    data_remover = data_remover.drop(columns =[3,6,9])

    # making the 1st row as header
    data_remover.columns = data_remover.iloc[0]
    data_remover = data_remover.drop(index=0).reset_index(drop=True)
    # return the fetched answer
    return data_remover

# adding a function to resolve missed / corrupeted data in csv
def corrupt_finder(data):
    # this function fix the corrupted details like NAN, None, random gibrish etc..
    data = data.replace(r'^\s*$', "Corrupted", regex=True) # it replaces only empty/ blank cell with "Corrupted" Tag
    data = data.fillna("Corrupted") # it replaces only NaN and None Value
    data = data.replace("None", "Corrupted") # replace None -> corrupted at start of ocr

    # retun the data to show!
    return data

# this function for resolving the corrupted data (aka ask the user to fill the corrupted field)
def corrupt_fixer(data):
    # loops for iterating over the table based on index and colums!
    for row in data.index:
        for column in data.columns:
            # accessing the data!
            store_data = data.at[row, column]
            # condition to check if data is corrupted
            if store_data == "Corrupted":
                # getting 1st colums are day
                day = data.at[row, data.columns[0]]
                # telling user to manually input the field
                print(f"\n[Fox]: Couldn't read this cell — Day: {day}, Period: {column}")
                # getting the input to fill the field
                fix = input("[Fox]: What should i say this? (or type 'skip'): ").strip()
                # if input is not skip it enters the data to the field
                if fix.lower() != "skip":
                    # inserting the input data to the csv
                    data.at[row, column] = fix
    # returning the data
    return data

# adding another function to see / review and edit the table!
def review_edit(data):
    print("[Fox]: Here's your schedule.....")
    # .to_string() = forces to print rows and column + convert entier table into string!
    print(data.to_string())

    try:
        while True:
            choice = input("\n[Fox]: Want to edit a cell? (yes/no): ").strip().lower()
            if choice != "yes":
                break

            day_input = input("[Fox]: Which day?: ").strip()
            # this checks for the matching data in all the rows and cols hehehe
            matches = data[data[data.columns[0]].str.lower() == day_input.lower()]

            # if matches is empty, notify user and continue (continue means below period and then repeat till either user quit or got correct input)
            if matches.empty:
                print("[Fox]: Day not found, Try again!")
                continue

            # check rows for matches
            row = matches.index[0]
            print("\n[Fox]:Periods for {day_input}: ")
            # this iterate over columns
            for column in data.columns[1:]:
                # prints the founded data + that data.loc will look through each row and column and prints the required found value!
                print(f" {column} -> {data.loc[row, column]}")

            # asking edit for period
            period = input("[Fox]: Which period do you want to edit?: ").strip() # ask user what to edit
            # check period is present in table
            if period not in data.columns:
                print("[Fox]: Period not found, try again. ") # this notifies the user and it prompts to tryagain forgot? while loop that's why!
                continue

            new_value = input(f"[Fox]: New value for {day_input} / {period}: ").strip()
            data.at[row, period] = new_value
            print("[Fox]: Updated.\n")
        return data
    except Exception as e:
        print(f"[Fox]: Something went wrong — {e}")
        pass
    except ValueError:
        pass

# adding function again and again to fix the formant (long format table to match the csv)
def longformat_table(data):
    # data adding
    long_data = {"day": [], "subject": [], "time_start": [], "time_end": [], "books_needed": []}

    try:
        # adding periods and day column
        period_column  = data.columns[1:]
        days_column = data.columns[0]

        # iterate through the column and fix the table
        for _, row in data.iterrows():
            # iterating days row
            day = row[days_column]
            for period in period_column:
                # iterating column row for period!
                subject = row[period]
                if pd.isna(subject) or str(subject).strip() == "":
                    continue

                # adding things so csv won't messed up like start and stop
                time = str(period).replace("(", "").replace(")", "").split("-") # this replace and splits based on the table
                time_start = time[0].strip() if len(time) > 0 else "" # adding the start time to the table
                time_end = time[1].strip() if len(time) > 1 else "" # adding tthe end time to the table

                # appending things to the long data to store! and update!
                long_data["day"].append(day)  # adding day
                long_data["subject"].append(str(subject).strip())  # adding subject
                long_data["time_start"].append(time_start) # adding start time
                long_data["time_end"].append(time_end) # adding end time
                long_data["books_needed"].append("")  # adding details for required books based on period
        return pd.DataFrame(long_data)
    
    # to catch the error and run program even after the error
    except Exception as e:
        print(f"[Fox]: Something went wrong while reshaping the table — {e}")
        return None

# calling function
if __name__ == "__main__":
    df = extract_table("Schedule_Bot/Data/Schedule.png")
    df = corrupt_finder(df)
    df = corrupt_fixer(df)
    df = review_edit(df)

    long_data = longformat_table(df)
    print(long_data)

    from Schedule_Bot.schedule_pharaser import csv_saver
    from Path_mapper import SCHEDULE_CSV
    csv_saver(long_data, SCHEDULE_CSV)
    print(f"\n[Fox]: Saved to {SCHEDULE_CSV}")