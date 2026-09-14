# seeing annie's output like what she does via text / test

import json

from agent.annie.annie import Annie, OllamaAnnieBackend
from agent.julie.julie import Julie, OllamaReasoningBackend
from agent.ollama.client import OllamaClient


def main():
    client = OllamaClient()

    # Julie
    julie = Julie(
        OllamaReasoningBackend(client)
    )

    # Annie
    annie = Annie(
        OllamaAnnieBackend(client)
    )

    user_request = (
        "How's my Downloads folder looking? "
        "I think I have to organise it, can you do that?"
    )

    print("=" * 60)
    print("ANNIE — REAL OLLAMA DEMO")
    print("=" * 60)

    print("\nUSER REQUEST:")
    print(user_request)

    # Step 1: Julie understands the request
    julie_result = julie.reason(user_request)

    print("\n" + "-" * 60)
    print("JULIE")
    print("-" * 60)

    print("\nEXPANDED TASK:")
    print(julie_result.expanded_task)

    print("\nPLAN:")
    for index, step in enumerate(julie_result.plan, 1):
        print(f"{index}. {step}")

    print("\nUNCERTAINTY:")
    for item in julie_result.uncertainty:
        print(f"- {item}")

    # Step 2: Annie structures Julie's reasoning
    annie_result = annie.structure(julie_result)

    print("\n" + "-" * 60)
    print("ANNIE")
    print("-" * 60)

    print("\nINTERPRETATION:")
    print(annie_result.interpretation)

    print("\nREQUIREMENTS:")
    for item in annie_result.requirements:
        print(f"- {item}")

    print("\nCONSTRAINTS:")
    for item in annie_result.constraints:
        print(f"- {item}")

    print("\nTECHNICAL HANDOFF:")
    print(annie_result.technical_handoff)

    print("\nCLARIFICATION NEEDED:")
    if annie_result.clarification_needed:
        for item in annie_result.clarification_needed:
            print(f"- {item}")
    else:
        print("- None")

    print("\n" + "=" * 60)
    print("ANNIE HANDOFF COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()