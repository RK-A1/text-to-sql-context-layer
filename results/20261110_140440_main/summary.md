# 20261110_140440_main

## Execution accuracy by arm (%)

| arm        |   answers |   EX original label |   EX corrected label |   strict, original |   strict, corrected |   no answer |   answered on last call |   SAT answers filtering rtype (%) |   cost per answer ($) |   total cost ($) |
|:-----------|----------:|--------------------:|---------------------:|-------------------:|--------------------:|------------:|------------------------:|----------------------------------:|----------------------:|-----------------:|
| schema     |        90 |                40   |                 41.1 |               36.7 |                37.8 |           3 |                      16 |                              19.4 |               0.00266 |           0.2396 |
| dictionary |        90 |                43.3 |                 38.9 |               37.8 |                33.3 |           1 |                      12 |                               9.5 |               0.00232 |           0.2085 |
| hints      |        90 |                67.8 |                 57.8 |               64.4 |                54.4 |           2 |                       4 |                               7.9 |               0.00184 |           0.1659 |
| context    |        90 |                40   |                 44.4 |               33.3 |                37.8 |           3 |                       8 |                             100   |               0.00218 |           0.1959 |

## The 9 questions whose two labels give different answers

| arm        |   answers |   matched original only |   matched corrected only |   matched neither |
|:-----------|----------:|------------------------:|-------------------------:|------------------:|
| schema     |        27 |                       5 |                        6 |                16 |
| dictionary |        27 |                       9 |                        5 |                13 |
| hints      |        27 |                      14 |                        5 |                 8 |
| context    |        27 |                       5 |                        9 |                13 |

## Lead over schema only on the corrected label (points)

|            |   lead over schema |   95% low |   95% high |
|:-----------|-------------------:|----------:|-----------:|
| dictionary |               -2.2 |     -11.1 |        6.7 |
| hints      |               16.7 |       4.4 |       30   |
| context    |                3.3 |      -8.9 |       16.7 |
