package internal

import "time"

type Resources struct {
	CPUCores float64 `json:"cpu_cores"`
	MemoryMB float64 `json:"memory_mb"`
}

type CostDeployment struct {
	Name            string
	CurrentRequests Resources `json:"current_requests"`
	CurrentUsage    Resources `json:"current_usage"`
}

type ForecastDeployment struct {
	Name           string
	PredictPeak24h Resources `json:"predict_peak_24h"`
}

type ClusterTotals struct {
	VmCount float64 `json:"vm_count"`
	Cost    float64 `json:"current_hourly_cost"`
}

type CostPayload struct {
	Source        string           `json:"source"`
	Timestamp     time.Time        `json:"timestamp"`
	Namespace     string           `json:"namespace"`
	ClusterTotals ClusterTotals    `json:"cluster_totals"`
	Deployments   []CostDeployment `json:"deployments"`
}

type ForecastPayload struct {
	Source      string               `json:"source"`
	Timestamp   time.Time            `json:"timestamp"`
	Namespace   string               `json:"namespace"`
	Deployments []ForecastDeployment `json:"deployments"`
}
