# Research Sourcing Doctrine 2026-03-24

Status: active operating doctrine

## Purpose

This repo is allowed and expected to learn aggressively from the frontier memory literature and open research ecosystem.

That includes, when useful:

- arXiv papers
- Hugging Face paper pages
- official project repos
- official benchmark repos
- public technical writeups for relevant memory systems

## What this means operationally

When the next architecture move is unclear, the research loop should feel free to:

1. inspect recent papers and paper pages for benchmark-relevant ideas
2. study public memory-system repos and implementation notes
3. borrow patterns from strong systems if they fit the benchmark pressure
4. update the repo doctrine when a borrowed pattern survives real evaluation

This is not optional purity behavior.
It is part of how the chip is supposed to work.

## Allowed inspiration sources

High-priority source classes:

- benchmark papers and official benchmark docs
- memory-system papers on temporal reasoning, long-context recall, profile memory, relation memory, consolidation, and retrieval routing
- Hugging Face paper pages when they provide easier access to paper metadata, summaries, linked code, or implementation surfaces
- official repos for systems such as `Supermemory`, `Mastra`, `Graphiti`, `A-Mem`, `LightMem`, `SimpleMem`, `MemoryOS`, `MemOS`, and adjacent systems

## Discipline rules

The project must keep four evidence classes separate:

1. inspiration
2. public claim
3. local reproduction
4. promoted doctrine

Rules:

- do not confuse a paper claim with a reproduced result
- do not describe a borrowed idea as proven in this repo until it survives our benchmark loop
- do not hide licensing or attribution constraints
- do not let benchmark marketing language become repo doctrine without evidence
- when borrowing an idea or implementation pattern from a GitHub repo, record the source repo and its declared license if it is `MIT` or `Apache-2.0`
- if a borrowed idea comes from an `MIT` or `Apache-2.0` repo, document that borrowing in the attribution surfaces rather than relying on memory or informal notes
- if the license is not clearly `MIT` or `Apache-2.0`, treat it as a separate review lane before copying implementation details

## Promotion rule

A pattern from arXiv, Hugging Face paper pages, or another memory system can influence the design immediately.

But it only becomes doctrine after:

1. the source is pinned clearly
2. attribution is clean, including repo and license notes where the source repo is `MIT` or `Apache-2.0`
3. the implementation is understandable
4. the benchmark behavior improves honestly

## Current implication

This repo should feel free to use frontier memory research as fuel while staying strict about the difference between:

- what others reported
- what we have actually measured

That distinction is mandatory.

## GitHub borrowing rule

When a design move is inspired by a GitHub repo:

1. identify the exact repo
2. identify the declared license
3. if the repo is `MIT` or `Apache-2.0`, document the borrowing in the repo attribution surfaces
4. if the repo is not clearly `MIT` or `Apache-2.0`, do not treat it as a normal borrow path until the license position is reviewed
