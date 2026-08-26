"""A while loop whose common path continues, as pytest's argument walk does.

The loop's test has to be re-evaluated on every iteration. A ``continue`` that
skips the refresh leaves the loop testing a stale value, so it never ends.
"""


def walk(args):
    seen = []
    i = 0
    n = len(args)
    while i < n:
        opt = args[i]
        i += 1
        if not opt.startswith("-p"):
            continue
        seen.append(opt)
    return seen


def nested(rows):
    total = 0
    outer = 0
    while outer < len(rows):
        for value in rows[outer]:
            if value < 0:
                continue
            total += value
        outer += 1
    return total


print(walk(["a", "-pfoo", "b", "-pbar", "c"]))
print(nested([[1, -2, 3], [-4, 5]]))
