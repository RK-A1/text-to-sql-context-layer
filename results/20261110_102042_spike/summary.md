# 20261110_102042_spike

## Execution accuracy by arm (%)

| arm        |   answers |   EX original label |   EX corrected label |   strict, original |   strict, corrected |   no answer |   answered on last call |   SAT answers filtering rtype (%) |   cost per answer ($) |   total cost ($) |
|:-----------|----------:|--------------------:|---------------------:|-------------------:|--------------------:|------------:|------------------------:|----------------------------------:|----------------------:|-----------------:|
| schema     |        90 |                41.1 |                 38.9 |               34.4 |                32.2 |          18 |                       0 |                               7.1 |               0.00236 |           0.2123 |
| dictionary |        90 |                41.1 |                 36.7 |               33.3 |                28.9 |          11 |                       0 |                               8.8 |               0.00203 |           0.1826 |
| hints      |        90 |                58.9 |                 48.9 |               57.8 |                47.8 |          15 |                       0 |                               9.7 |               0.00194 |           0.1749 |
| context    |        90 |                36.7 |                 35.6 |               34.4 |                33.3 |          13 |                       0 |                              93.8 |               0.00196 |           0.1765 |

## The 9 questions whose two labels give different answers

| arm        |   answers |   matched original only |   matched corrected only |   matched neither |
|:-----------|----------:|------------------------:|-------------------------:|------------------:|
| schema     |        27 |                       5 |                        3 |                19 |
| dictionary |        27 |                       8 |                        4 |                15 |
| hints      |        27 |                      10 |                        1 |                16 |
| context    |        27 |                       5 |                        4 |                18 |

## Lead over schema only on the corrected label (points)

|            |   lead over schema |   95% low |   95% high |
|:-----------|-------------------:|----------:|-----------:|
| dictionary |               -2.2 |      -8.9 |        4.4 |
| hints      |               10   |      -3.3 |       23.3 |
| context    |               -3.3 |     -12.2 |        3.3 |
