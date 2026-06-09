# Project Rules

## Architecture

Follow:

Clean Architecture
SOLID
DDD

## Coding Rules

Python 3.9+

Type Hint Required

No global variables

Unit Test Required

Coverage > 80%

## Upgrade Safety Rules

Never execute real upgrade during tests.

Never modify grub in tests.

Never reboot host in tests.

All system operations must be abstracted.

## Development Strategy

Small incremental changes.

One feature per commit.

Always add tests.

Always update docs.