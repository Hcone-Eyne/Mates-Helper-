# this part is about auto identy the logic of arithmetic operations

# v2 added: This now supports more than 2 numbers, with proper order
# this program limits are, only 2 numbers at a time



# importing nessary modules!
from rich.console import Console
import re

# this function is going to handle all arithmetic operations and extraction
def operation_finder(num):

    # tokenizing the input string to extract numbers and operators
    tokens = re.findall(r'\d+\.?\d*|[+\-*/]', num)

    # checking if user entered valid expression
    if not tokens:
        print("[Fox]: Invalid expression. Please enter a valid arithmetic expression.")
        return

    # this part is ment to handle negative integers!
    merged = []  # (handles cases like "-5+3" or "5*-3" where '-' means sign, not subtraction)
    # initialising the i ahh
    i = 0
    # this loop to iterate to tokens
    while i < len(tokens):
        # reference toke value
        tok = tokens[i]
        # this conditions checks for nessary tokens like "-"
        if tok == "-" and (i == 0 or merged[-1] in "+-*/" ) and i+1 < len(tokens):
            merged.append("-" + tokens[i+1])
            # increment value of i
            i+=2
            continue
        # if those condition isn't meet in the current token this gets executed
        merged.append(tok)
        i+= 1

    # merged tokens is used also used by postfix function below
    tokens = merged


    # this function is going to convert tokens into int / float
    def to_num(tokens):
        # this statement checks if the string "tokens" contains decimal value.....
        # if value present convert to float else, it convert to int 
        return float(tokens) if "." in tokens else int(tokens)

    # we gonna use stack to handle problem 
    # stack is going to pritrize those math rules "BODMAS"!
    stack = [to_num(tokens[0])]  # initialize stack with the first number

    i = 1  # setting up value to start from!

    # initializing the loop to iterate through the tokens
    while i < len(tokens):
        # initialising those variables to store the operation and number
        operation = tokens[i]
        number = to_num(tokens[i + 1])

        # if the operation is multiplication or division, perform it immediately
        if operation in  ("*", "/"):
            # if * or / is found, pop the last number from the stack and perform the operation with the current number
            preview = stack.pop()
            # performing the operation and pushing the result back to the stack
            stack.append(preview * number if operation == "*" else preview / number)
        else:
            # if it's other operation, just push the operation and number to the stack
            stack.append(operation)
            stack.append(number)
        # incrementing i to keep the flow to iterate to all values
        # also i += 2 because they all consume 2 tokens at a time
        i+= 2

    # this part going to do + and -
    result = stack[0] # initialize result with the first number in the stack
    i = 1
    # initializing the loop to iterate through the stack
    while i < len(stack):
        # initialising those variables to store the operation and number
        operation = stack[i]
        number = stack[i + 1]

        # performing the operation and updating the result
        result = result + number if operation == "+" else result - number

        # incrementing i to keep the flow to iterate to all values in stack!
        # also i += 2 because they all consume 2 tokens at a time
        i += 2
    # returning result
    return result

# Note to myself, Those 2 while loop aren't parallel those are sequential, first one is for * and / and second one is for + and -.
# they aren't executing infinitely!
if  __name__ == "__main__":
    operation_finder("12+3*2")