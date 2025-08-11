# Welcome

## Relevance score

This is the quickly-derived formula to order the results roughly from most to least relevant.

$$
score = (\frac{\sum_{t=1}^n (i\_t \cdot w\_t \cdot w\_q) + (i\_d \cdot w\_d \cdot w\_q) + (i\_b \cdot w\_b \cdot w\_q) + (i\_u \cdot w\_u \cdot w\_q)}{s + 1}) * a
$$

| Symbol | Description                                                       |
| ------ | ----------------------------------------------------------------- |
| $t$    | Search term                                                       |
| $n$    | Total search terms (split by spaces but not in quotes)            |
| $i\_t$ | Number of instances of the search string found in the title       |
| $i\_d$ | Number of instances of the search string found in the description |
| $i\_b$ | Number of instances of the search string found in the body        |
| $i\_u$ | Number of instances of the search string found in the URL         |
| $s$    | Number of forward slashes in the URL                              |

### Variables

| Variable | Description                                           | Default value              |
| -------- | ----------------------------------------------------- | -------------------------- |
| $w\_t$   | The weighting of an instance found in the title       | `250`                      |
| $w\_d$   | The weighting of an instance found in the description | `50`                       |
| $w\_b$   | The weighting of an instance found in the body        | `5`                        |
| $w\_u$   | The weighting of an instance found in the URL         | `1`                        |
| $w\_q$   | Extra weighting if the search term $t$ is quoted      | `1000` if quoted else `1`  |
| $a$      | The weighting of a URL that is considered archived    | `0.5` if archived else `1` |
