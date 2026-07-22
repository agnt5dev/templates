// Functions for the weather agent.
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"time"

	"agnt5.dev/sdk-go/agnt5"
)

var httpClient = &http.Client{Timeout: 10 * time.Second}

type geocodeResponse struct {
	Results []struct {
		Name      string  `json:"name"`
		Latitude  float64 `json:"latitude"`
		Longitude float64 `json:"longitude"`
		Country   string  `json:"country"`
		Admin1    string  `json:"admin1"`
	} `json:"results"`
}

type forecastResponse struct {
	Current struct {
		Temperature2m      float64 `json:"temperature_2m"`
		RelativeHumidity2m int     `json:"relative_humidity_2m"`
		WindSpeed10m       float64 `json:"wind_speed_10m"`
	} `json:"current"`
}

func getJSON(ctx context.Context, rawURL string, query url.Values, out any) error {
	u, err := url.Parse(rawURL)
	if err != nil {
		return err
	}
	u.RawQuery = query.Encode()

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, u.String(), nil)
	if err != nil {
		return err
	}
	resp, err := httpClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("%s HTTP %d", rawURL, resp.StatusCode)
	}
	return json.NewDecoder(resp.Body).Decode(out)
}

// fetchWeatherData geocodes a location and fetches its current weather.
func fetchWeatherData(ctx context.Context, location string) (WeatherData, error) {
	var geo geocodeResponse
	if err := getJSON(ctx, geocodingAPIURL, url.Values{
		"name":  {location},
		"count": {"1"},
	}, &geo); err != nil {
		return WeatherData{}, err
	}
	if len(geo.Results) == 0 {
		return WeatherData{}, fmt.Errorf("location not found: %s", location)
	}
	place := geo.Results[0]

	var forecast forecastResponse
	if err := getJSON(ctx, weatherAPIURL, url.Values{
		"latitude":  {fmt.Sprintf("%f", place.Latitude)},
		"longitude": {fmt.Sprintf("%f", place.Longitude)},
		"current":   {"temperature_2m,relative_humidity_2m,wind_speed_10m"},
	}, &forecast); err != nil {
		return WeatherData{}, err
	}

	tempC := forecast.Current.Temperature2m
	return WeatherData{
		Location:     place.Name,
		Latitude:     place.Latitude,
		Longitude:    place.Longitude,
		TemperatureC: tempC,
		TemperatureF: tempC*9/5 + 32,
		Humidity:     forecast.Current.RelativeHumidity2m,
		WindKph:      forecast.Current.WindSpeed10m,
		Country:      place.Country,
		Region:       place.Admin1,
	}, nil
}

type GetWeatherDataInput struct {
	Location string `json:"location"`
}

// getWeatherData is the registered Function wrapper around fetchWeatherData.
func getWeatherData(ctx *agnt5.Context, in GetWeatherDataInput) (WeatherData, error) {
	return fetchWeatherData(ctx, in.Location)
}
