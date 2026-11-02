EXPLORATORY analyses (not part of the frozen M9 protocol; the frozen results in ../*.json are unchanged).

latency_sensitivity.json   scripts/m9_latency_sensitivity.py: B's latency as physical-completion latency (what the
                           frozen harness measured) and as successful-delivery latency (what the protocol text states),
                           360 confirmatory runs re-executed (every fingerprint equal to the published run).
substitutes.json           scripts/m9_substitutes.py: available / detectable / selectable / selected / executed
                           substitute paths during the M9-C outage (X4, X4b), executability checked over every gantry on
                           the transfer's route.
substitutes_v1_source_bay_only_SUPERSEDED.json
                           the first version of the same analysis, which checked only the source bay's gantry and so
                           counted substitutes whose last leg needs the failed bay-0 gantry as executable. Kept for the
                           record; superseded by substitutes.json. Its "selectable" counts are wrong.
