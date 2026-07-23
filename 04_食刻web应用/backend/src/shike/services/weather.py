# -*- coding: utf-8 -*-
"""高德天气服务。"""

from __future__ import annotations

import httpx

from shike.config import AppConfig


class WeatherService:
    def __init__(self, config: AppConfig):
        self.api_key = config.weather.api_key

    async def get_weather(self, city: str) -> dict[str, str]:
        if not self.api_key or not city:
            return {"city": city, "weather": "未知", "temperature": "", "report_time": ""}

        async with httpx.AsyncClient(timeout=10) as client:
            geo_resp = await client.get(
                "https://restapi.amap.com/v3/config/district",
                params={"keywords": city, "subdistrict": 0, "key": self.api_key},
            )
            geo_data = geo_resp.json()
            adcode = ""
            if geo_data.get("districts"):
                adcode = geo_data["districts"][0].get("adcode", "")

            if not adcode:
                return {"city": city, "weather": "未知", "temperature": "", "report_time": ""}

            weather_resp = await client.get(
                "https://restapi.amap.com/v3/weather/weatherInfo",
                params={"city": adcode, "key": self.api_key, "extensions": "base"},
            )
            weather_data = weather_resp.json()
            lives = weather_data.get("lives", [])
            if lives:
                live = lives[0]
                return {
                    "city": live.get("city", city),
                    "weather": live.get("weather", ""),
                    "temperature": f"{live.get('temperature', '')}C",
                    "report_time": live.get("reporttime", ""),
                }
        return {"city": city, "weather": "未知", "temperature": "", "report_time": ""}
