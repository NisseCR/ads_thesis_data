# ADS Thesis Data Scraper

This repository contains a Python scraper for collecting audio-file and soundscape metadata.

## Project Context

The audio repository contains a large collection of cross-domain audio mixes. These soundscapes combine different types of sound sources, including:

- melodic sounds
- tonal sounds
- environmental sounds
- natural ambience
- synthetic textures
- human-made or mechanical audio elements

The goal of this project is to collect structured data about the available soundscapes and the audio files used to construct them. This data can then be used for further analysis of how sound categories, audio layers, and soundscape compositions relate to each other.

## Process

The scraper first builds a manifest of available soundscape URLs, then iterates over this manifest to collect audio-file metadata for each soundscape.
