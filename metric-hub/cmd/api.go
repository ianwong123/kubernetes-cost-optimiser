package main

import (
	"encoding/json"
	"fmt"
	"net/http"

	"github.com/ianwong123/kubernetes-cost-optimiser/metric-hub/internal"
)

type APIServer struct {
	Validator internal.ValidatorInterface
}

// cosntructor
func NewAPIServer() *APIServer {
	return &APIServer{
		Validator: internal.NewValidator(),
	}
}

// start http server
func (s *APIServer) Start() error {
	mux := http.NewServeMux()
	mux.HandleFunc("POST /metrics/cost", s.handleCostEngine)
	mux.HandleFunc("POST /metrics/forecast", s.handleForecast)

	return http.ListenAndServe(":8008", mux)
}

// handler function for POST /metrics/cost request
func (s *APIServer) handleCostEngine(w http.ResponseWriter, r *http.Request) {
	var payload internal.CostPayload

	dec := json.NewDecoder(r.Body)
	if err := dec.Decode(&payload); err != nil {
		http.Error(w, "Bad request", http.StatusBadRequest)
		return
	}

	if err := s.Validator.ValidateCostPayload(&payload); err != nil {
		http.Error(w, "Invalid JSON format", http.StatusBadRequest)
		return
	}

	fmt.Println("Received post request for /metrics/cost")
	w.WriteHeader(http.StatusCreated)
	w.Write([]byte("Cost payload accepted"))

}

// handler function for POST /metrics/forecast
func (s *APIServer) handleForecast(w http.ResponseWriter, r *http.Request) {
	var payload internal.ForecastPayload
	dec := json.NewDecoder(r.Body)
	if err := dec.Decode(&payload); err != nil {
		http.Error(w, "Bad request", http.StatusBadRequest)
		return
	}

	if err := s.Validator.ValidateForecastPayload(&payload); err != nil {
		http.Error(w, "Invalid JSON format", http.StatusBadRequest)
		return
	}

	fmt.Println("Received post request for /metrics/forecast")
	w.WriteHeader(http.StatusCreated)
	w.Write([]byte("Forecast payload accepted"))

}
