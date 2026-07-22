// Data models for the weather agent.
package main

const (
	geocodingAPIURL = "https://geocoding-api.open-meteo.com/v1/search"
	weatherAPIURL   = "https://api.open-meteo.com/v1/forecast"

	serviceName    = "weather-agent"
	serviceVersion = "1.0.0"
)

// WeatherData is weather information for a location.
type WeatherData struct {
	Location     string  `json:"location"`
	Latitude     float64 `json:"latitude"`
	Longitude    float64 `json:"longitude"`
	TemperatureC float64 `json:"temperature_c"`
	TemperatureF float64 `json:"temperature_f"`
	Humidity     int     `json:"humidity"`
	WindKph      float64 `json:"wind_kph"`
	Country      string  `json:"country,omitempty"`
	Region       string  `json:"region,omitempty"`
}
