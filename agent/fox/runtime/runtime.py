# this program going to handle the runtime of the fox club member task btw, it doesn't perforrm any action itself/


# creating a runtime class
class Runtime:

    # starting the initial process.....
    def __init__(self, julie = None,gwen = None, selina = None):
        self.julie =julie
        self.gwen = gwen
        self.selina = selina

    # this function is going to process the user request through Fox which is this function!
    def handle(self, user_input: str):
        # create a conditions to check the input values
        if not isinstance(user_input, str):
            raise TypeError("[Fox]: User input isn't string.....")

        user_input = user_input.strip()

        # else return all
        if not user_input:
            return ""

        # agent pipline will be implemented incrementally.....
        return user_input

