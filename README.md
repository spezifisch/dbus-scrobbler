# dbus scrobbler

Submit listened songs to Audioscrobbler services such as last.fm or libre.fm.

Supported are audio players with an MPRIS2 interface such as Clementine or Audacious.

## Dependencies

* python >= 3.5
* pypoetry (`pip install poetry` or `apt install python3-poetry`)
* the rest will be installed in a virtualenv via poetry

## Installation

```bash
$ poetry up
```

## Configurations

```bash
$ cp config.yaml.example config.yaml
$ vim config.yaml
```

## Usage

```bash
$ poetry run scrobbler config.yaml
```

