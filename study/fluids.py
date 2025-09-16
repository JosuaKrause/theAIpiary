#!/usr/bin/env python
import copy


def init_buckets() -> dict[str, dict[str, float]]:
    return {
        "a": {"milk": 1.0},
        "b": {},
        "c": {"formula": 1.0},
    }


def print_buckets(buckets: dict[str, dict[str, float]]) -> None:
    print()
    contents = totals(buckets)
    for bucket, bucket_contents in buckets.items():
        print(f"{bucket=} {contents[bucket]:.3f}")
        for fluid, amount in bucket_contents.items():
            print(f"  {fluid}={amount:.3f}")
        print()


def totals(buckets: dict[str, dict[str, float]]) -> dict[str, float]:
    return {
        bucket: sum(contents.values())
        for bucket, contents in buckets.items()
    }


def move(
        buckets: dict[str, dict[str, float]],
        from_bucket: str,
        to_bucket: str,
        amount: float) -> str | None:
    contents = totals(buckets)
    from_amount = contents[from_bucket]
    if from_amount == 0.0:
        return None
    to_amount = 1.0 - contents.get(to_bucket, 0.0)
    moving_amount = min(amount, from_amount, to_amount)
    notes = f"moving {moving_amount} from {from_bucket} to {to_bucket}"
    print(notes)
    move_content = {
        fluid: amount * moving_amount / from_amount
        for fluid, amount in buckets[from_bucket].items()
    }
    for fluid, fluid_amount in move_content.items():
        buckets[from_bucket][fluid] -= fluid_amount
        bucket_content = buckets.setdefault(to_bucket, {})
        bucket_content[fluid] = bucket_content.get(fluid, 0.0) + fluid_amount
    return notes


def interpret(buckets: dict[str, dict[str, float]]) -> None:
    initial_buckets = copy.deepcopy(buckets)
    moves = []
    while True:
        print_buckets(buckets)
        print("commands:")
        print("move [from] [to] [amount]")
        print("quit")
        line = input("> ")
        if line == "quit":
            break
        cmd = line.removeprefix("move ")
        if line == cmd:
            print("invalid command")
            continue
        try:
            from_bucket, to_bucket, amount_str = cmd.split(maxsplit=2)
            notes = move(buckets, from_bucket, to_bucket, float(amount_str))
            if notes is not None:
                moves.append(notes)
        except ValueError:
            print("invalid command")
            continue
    print()
    print_buckets(initial_buckets)
    for notes in moves:
        print(notes)
    print_buckets(buckets)


if __name__ == "__main__":
    interpret(init_buckets())
