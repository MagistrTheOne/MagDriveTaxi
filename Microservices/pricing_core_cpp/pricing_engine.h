#pragma once

#include <string>
#include <map>

namespace magadrive {

enum class VehicleClass {
    COMFORT,
    BUSINESS,
    XL
};

struct PricingRequest {
    double distance_m;
    VehicleClass vehicle_class;
    int base_price_rub;
    double surge_multiplier;
    double time_of_day_multiplier;
};

struct PricingResponse {
    int final_price_rub;
    double distance_multiplier;
    double class_multiplier;
    double surge_multiplier;
    double time_multiplier;
    std::string currency;
};

class PricingEngine {
public:
    PricingEngine();
    
    PricingResponse calculatePrice(const PricingRequest& request);
    
    // Геттеры для множителей
    double getDistanceMultiplier(double distance_m) const;
    double getClassMultiplier(VehicleClass vehicle_class) const;
    double getTimeOfDayMultiplier() const;
    
private:
    // Базовые множители для разных классов
    std::map<VehicleClass, double> class_multipliers_;
    
    // Множители по расстоянию
    double base_distance_multiplier_;
    double long_distance_threshold_m_;
    double long_distance_multiplier_;
    
    // Множители по времени суток
    double peak_hour_multiplier_;
    double night_hour_multiplier_;
};

} // namespace magadrive
