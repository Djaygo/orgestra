"""The expo floor of /town: sponsors and the tool seeds they sell, from resources/sponsors.toml."""

from __future__ import annotations

import tomllib
from importlib import resources

from pydantic import BaseModel, ConfigDict, Field, model_validator

BUNDLE_SHARE = 0.8  # a whole stand costs this share of its seeds' prices, rounded down


class Seed(BaseModel):
    """A tool seed: the idea for an agent harness tool (a skill, hook or check) before its code."""

    model_config = ConfigDict(frozen=True)

    slug: str
    sponsor: str
    name: str
    product: list[str]
    price: int = Field(gt=0)
    hook: str
    pitch: str
    problem: str
    fires: str
    mechanism: str
    gates: str


class Sponsor(BaseModel):
    model_config = ConfigDict(frozen=True)

    slug: str
    name: str
    tagline: str
    color: str = Field(pattern=r"^#[0-9a-f]{6}$")


class Expo(BaseModel):
    model_config = ConfigDict(frozen=True)

    budget: int = Field(gt=0)
    sponsors: list[Sponsor]
    seeds: list[Seed]

    @model_validator(mode="after")
    def _every_seed_has_a_sponsor(self) -> Expo:
        known = {sponsor.slug for sponsor in self.sponsors}
        orphans = [seed.slug for seed in self.seeds if seed.sponsor not in known]
        if orphans:
            raise ValueError(f"seeds without a sponsor: {orphans}")
        return self

    def sponsor(self, slug: str) -> Sponsor | None:
        return next((sponsor for sponsor in self.sponsors if sponsor.slug == slug), None)

    def seeds_of(self, sponsor: Sponsor) -> list[Seed]:
        return [seed for seed in self.seeds if seed.sponsor == sponsor.slug]

    def bundle_price(self, sponsor: Sponsor) -> int:
        """frontend/src/town/bag.ts prices a complete stand the same way."""
        return int(sum(seed.price for seed in self.seeds_of(sponsor)) * BUNDLE_SHARE)


def load_expo() -> Expo:
    source = resources.files("orgestra.resources").joinpath("sponsors.toml").read_text(encoding="utf-8")
    return Expo.model_validate(tomllib.loads(source))
