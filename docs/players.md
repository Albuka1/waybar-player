# MPRIS diagnostics

Date: 2026-10-31. Yandex Music in Chromium.

## `playerctl -l`

```text
chromium.instance125864
```

## `playerctl -a metadata --format '{{playerName}} {{status}}'`

```text
chromium Paused
```

## Chromium (`chromium.instance125864`)

```text
$ playerctl -p chromium.instance125864 volume
1.000000
$ playerctl -p chromium.instance125864 shuffle
No player could handle this command
$ playerctl -p chromium.instance125864 loop
No player could handle this command
$ playerctl -p chromium.instance125864 volume 0.3
$ playerctl -p chromium.instance125864 volume   # after ~350 ms
1.000000
```

Conclusions:

- Chromium advertises a volume property, but setting it to `0.3` did not
  change the reported value (`1.000000`); the volume control is ineffective.
- Shuffle and loop are not supported; the popup hides those buttons.
- The volume fallback (`WAYBAR_PLAYER_VOLUME_FALLBACK`, default `sink`) is
  therefore required for this player.

## Firefox

```text
$ playerctl -l
chromium.instance125864
$ playerctl -p firefox volume
No players found
$ playerctl -p firefox metadata mpris:artUrl
No players found
```

Firefox was not running an MPRIS media session during this check, so its
`mpris:artUrl` could not be inspected. The Firefox artwork issue is not
reproduced here; it is not treated as a confirmed whitelist regression. When
Firefox is playing, `playerctl -p firefox metadata mpris:artUrl` should be
checked for scheme and path against the whitelist in `fetch_art()`.


## Post-fix note (0.2.2)

The Chromium check above was made while the player was **paused**. Under the
new rule the result is ambiguous: volume is classified only while
`status == playing`, and the mark is keyed by `(player, track id)`. The paused
observation therefore must not switch the slider to the system sink. A
playing-track check is still needed; after a track change the mark is cleared
and Chromium/YouTube can keep native volume independently.


## Ограничения Chromium

Chromium публикует **одну MPRIS-сессию на браузер**. Если в одной вкладке
играет Яндекс Музыка, а затем запускается YouTube, прежняя сессия не
возвращается, пока в её вкладке снова не нажать play. `playerctl` видит только
текущую сессию, поэтому `loop`/`shuffle` могут относиться к YouTube, даже если
визуально открыта Яндекс Музыка. Это не кеш в `waybar-player`: приложение
перечитывает поддержку при каждом refresh и скрывает кнопки при ошибке/пустом
ответе, но не может увидеть неактивную вкладку браузера.

Проверка:

```bash
playerctl -l
playerctl -a metadata --format '{{playerName}} | {{status}} | {{title}} | {{mpris:trackid}}'
playerctl loop
playerctl shuffle
```

Если в `playerctl -l` одна строка `chromium.instance...`, значит видна только
одна сессия. Чтобы вернуть Яндекс Музыку, нажмите play в её вкладке; после
этого проверьте `playerctl loop` снова.
