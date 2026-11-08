# Search Simulator

Estimate how a document search could perform when it runs across several computers. Everything runs locally. No live document searches or AI answer requests are sent when you estimate a scenario.

## Open it

1. Run `start.command` in this folder. Keep its terminal window open.
2. Open **http://127.0.0.1:8010** in your browser.
3. Choose a setup and select **Estimate results**.

If dependencies are not installed yet, the launcher needs Python 3.12 and uses the included local installation packages for macOS Apple Silicon. For other systems, see the installation instructions in README.md.

## Choose a starting point

| Choice | What it does |
|---|---|
| **Use the tested setup** | Estimates based on real tests with one or three search computers. Computer count and match settings are fixed to those tests. |
| **Try different match settings** | Reuses recorded results from three computers to explore a stricter or looser match score. It does not perform a new search. |
| **Explore a different setup** | Lets you change the computer count and optional network/processing assumptions. These new setups have not been tested in real life. |

The computer count includes only computers that search documents. A separate computer coordinates the search and is not included in this count.

## Choose how to search

- **Search all computers at once:** ask every search computer at the same time, then combine the results.
- **Try the most relevant computer first:** rank computers by how relevant their documents seem, then check them one by one.
- **Try computers in a random order:** check randomly chosen computers one by one.
- **Keep all documents on one computer:** use one computer holding the entire collection.

The one-at-a-time methods stop after enough different passages meet the match score, or after checking every computer. A passage is a short section of a source document. A matching passage is not a guarantee of a correct answer.

## Understand the results

| Result | Meaning |
|---|---|
| **Average search time** | Average time to find and combine source passages, including coordination. |
| **Data transferred per search** | Captured requests and replies across the search network. Physical network overhead is not fully included. |
| **Time for 95% of searches** | 95% of simulated searches finish within this time; 5% take longer. Also called the 95th percentile or p95. |
| **Computers contacted** | Average number of search computers asked before stopping. It can be a decimal because it summarizes many simulated searches. |

1,000 milliseconds (ms) = 1 second. 1 kB = 1,000 bytes.

The **Include time for AI to write an answer** checkbox adds an estimated writing duration when source passages are found. It does not generate answer text.

## Optional settings

Defaults are enough for a first run. **Optional settings** explains each additional control beside its input. More simulation repetitions make the summary steadier; they do not create new real-world tests. Keep the same randomness seed and settings to reproduce a run.

In an assumed setup, the chance of choosing the right computer first is your routing assumption. It is not answer accuracy. Extra network delay, processing time changes, and connection speeds are assumptions as well. Larger collections, waiting queues, and many simultaneous searches are not modeled in this version.

## Save a scenario

Select **Download results (.csv)** to open a one-row summary in a spreadsheet. **More details and definitions** includes a full JSON download for technical use. Every calculation also saves its settings, summary and simulated rows under `results/ui_runs/` in the project folder.

These are estimates across a group of searches, not a promise for a specific question. A “Based on assumptions” label means the setup has not been validated with a matching physical experiment.
