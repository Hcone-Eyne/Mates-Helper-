# this part is about auto identy the logic of arithmetic operations

# this program limits are, only 2 numbers at a time

# TODO: add memory feature (need to have erase memory and auto memory catcher!), and support for more variable and need to add cli based graph

# importing nessary modules!
from rich.console import Console
# this function is going to handle all arithmetic operations and extraction
def operation_finder(num):

    # arithmetic operation list
    operation_list = ["+", "-", "/", "*"]

    # variables to hold the operation and the numbers
    left = "" # handles left side of list
    operator = None # currently operator value = 0
    right = "" # handles right side of list

    # creating a loop to check the operators and numbers
    for char in num:
        # this condition checks if the value is presented in operation list (find the operand!)
        if char in operation_list:
            operator = char
        # else it builds the left
        elif operator is None:
            left += char
        # after operand found, right side starts to get build!
        else:
            right += char

    # converting left and right to do arithmetic operations
    left = int(left)
    right = int(right)

    # appliying those arithmetic operations!
    if operator == "+":
        return left + right
    elif operator == "-":
        return left - right
    elif operator == "*":
        return left * right
    elif operator == "/":
        return left / right
    else:
        Console.print("Invalid input, Try again.....")

if  __name__ == "__main__":
    operation_finder("12+3")