# JASS English → Mizo Translator v1.1

An offline English → Mizo translation-memory explorer built around the
JASS Mizo parallel corpora.

The application uses a local SQLite translation database containing
**71,017 unique English--Mizo translation pairs** collected from the
available JASS Mizo parallel datasets. It is designed primarily as a
**translation-memory and corpus-evidence tool**, rather than a
machine-translation model.

## Features

-   **Offline operation** --- works entirely from the local SQLite
    database.
-   **English → Mizo translation lookup**.
-   **Smart Translate** mode for practical phrase and sentence matching.
-   **FTS5 search** for fast full-text retrieval.
-   Exact English phrase/sentence matches are prioritized.
-   Candidate ranking using corpus evidence and matching strength.
-   Groups duplicate translation candidates.
-   Shows the selected Mizo translation prominently.
-   Displays the English source/evidence behind the translation.
-   Shows translation frequency and match type.
-   Supports phrase and partial-word matching when an exact sentence is
    unavailable.
-   **Copy Mizo**, **Copy English**, and **Copy Both** actions.
-   Search-result limit control.
-   Clear search control.
-   Database information dialog.
-   Export of translation results.
-   Unicode/Mizo text support.

## Translation Database

The application uses:

``` text
JASS_English_Mizo_Translation.db
```

The database was built from:

``` text
Mizo_English_Parallel_20K.db
Mizo_Parallel_Corpus.db
```

Builder results:

  Item                          Count
  -------------------------- --------
  Parallel 20K rows            20,000
  Parallel corpus rows         51,022
  Unique translation pairs     71,017
  FTS records                  71,017

The database is treated as **read-only by the translator application**.
No database rebuild is required to run the translator.

## How It Works

The translator follows a translation-memory approach:

1.  Enter an English word, phrase, or sentence.
2.  The application searches the local translation database.
3.  Exact and strong matches are considered first.
4.  FTS5 retrieves additional corpus candidates.
5.  Candidates are ranked using available corpus evidence.
6.  Select a result to inspect the corresponding Mizo translation and
    source evidence.
7.  Copy the translation for use elsewhere.

For example:

``` text
English:
If you love someone.

Mizo:
Mi i hmangaih chuan.
```

The application therefore provides evidence-based translations from the
available Mizo corpus rather than inventing a translation when no
suitable corpus evidence exists.

## Match Types

The application can identify different levels of matching, including:

-   **Exact sentence / phrase**
-   **Prefix match**
-   **Phrase contained**
-   **Strong word overlap**
-   **Partial word overlap**
-   **Corpus / FTS match**

This makes the program useful even when the requested English sentence
does not occur verbatim in the database.

## Requirements

-   Windows
-   Python 3.14 or compatible Python version
-   PySide6
-   SQLite with FTS5 support
-   The accompanying translation database

Install the Python GUI dependency if necessary:

``` powershell
py -m pip install PySide6
```

## Installation

Keep these two files in the same directory:

``` text
JASS_English_Mizo_Translator_v1.1.py
JASS_English_Mizo_Translation.db
```

For example:

``` text
C:\Users\singh\Downloads\
    JASS_English_Mizo_Translator_v1.1.py
    JASS_English_Mizo_Translation.db
```

## Running

Open PowerShell and run:

``` powershell
cd C:\Users\singh\Downloads
py .\JASS_English_Mizo_Translator_v1.1.py
```

## Example Searches

Try:

``` text
love you
```

``` text
I love you
```

``` text
God loves us
```

``` text
come to our house
```

The database may return several corpus examples. Select a result to
inspect the translation evidence.

## Translation Memory, Not a Neural MT Model

This distinction is important.

JASS English → Mizo Translator v1.1 does **not** contain a neural
language model that independently generates Mizo sentences.

Instead, it uses:

``` text
English input
     ↓
Local SQLite / FTS5 search
     ↓
Corpus candidate retrieval
     ↓
Match and evidence ranking
     ↓
English–Mizo translation memory
     ↓
Mizo result
```

This approach has useful advantages for a local research tool:

-   Offline
-   Reproducible
-   Inspectable
-   Corpus-based
-   Source evidence available
-   No API or internet dependency
-   No external translation service required

It also means that translation quality is limited by the coverage,
quality, and diversity of the underlying parallel corpus.

## Project Position

This translator complements the other JASS Mizo tools:

``` text
JASS Mizo Corpus
       │
       ├── Mizo Lexicon
       │      └── Word-level exploration
       │
       ├── Mizo YouTube Sentiment
       │      └── Sentiment evidence
       │
       └── English–Mizo Translation Memory
              └── English → Mizo lookup
```

Together, these databases provide several complementary views of the
Mizo language:

-   vocabulary
-   corpus usage
-   English equivalents
-   translation pairs
-   example sentences
-   sentiment evidence

## Version 1.1 Status

**Status: Stable / Satisfactory**

Version 1.1 is intended as a practical local translation-memory
application using the existing 71K-pair database.

The current database and application should be treated as a stable
checkpoint rather than repeatedly rebuilt without a clear need.

## Future Expansion

Possible future work, if required, could include:

-   sentence segmentation
-   phrase assembly from multiple translation-memory entries
-   improved word-alignment information
-   translation confidence indicators
-   Mizo → English reverse lookup
-   bilingual concordance search
-   translation history
-   import/export of translation memories
-   additional verified English--Mizo parallel corpora
-   optional neural translation model integration

These would be extensions to the translation-memory foundation rather
than requirements for the current stable release.

## Credits

**JASS --- Jasvir AI / Language Tools**

Built as an offline language-resource application for exploring and
reusing available English--Mizo parallel corpus data.

## License

The application code and the underlying datasets may have different
licensing terms.

Check the original dataset repositories and source files for their
respective licenses before redistribution.

------------------------------------------------------------------------

**JASS English → Mizo Translator v1.1**\
*Offline translation memory • corpus evidence • phrase lookup • FTS5*
