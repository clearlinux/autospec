ONE ??= "first value"
ONE ?= "second value"

TWO ?= "first value"
TWO ??= "second value"

THREE ??= "first value"
THREE ?= "second value"
THREE = "third value"

FOUR = "first value"
FOUR += "second value"
FOUR =+ "third value"

FIVE = "first value"
FIVE .= "second value"
FIVE =. "third value"
