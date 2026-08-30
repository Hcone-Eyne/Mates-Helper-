# this part is about auto identy the logic of arithmetic operations

# this function is going to handle all arithmetic operations and extraction
def operation_finder(num):

    # converting string into list
    extractor = list(num)

    # arithmetic operation list
    operation_list = ["+", "-", "/", "*"]

    # operation store
    operand_variable = 0

    # temp variable for all arithmetic process
    temp_variable = 0

    # string_list = 0

    # this loop yea, go throigh the list and figure what is operand..
    for i in range(len(extractor)):
        if extractor[i] and extractor[i+1] is not operation_list:
            join = "".join(map(str,extractor[i]))
            print(join)
        if extractor[i] in operation_list:
            operand_variable = extractor[i]
            temp_variable = extractor.remove(extractor[i])
            temp_variable = extractor.append(operand_variable)
            print(extractor)
        if operand_variable == "+": print(extractor[i]+extractor[i+1])

operation_finder("12+12")