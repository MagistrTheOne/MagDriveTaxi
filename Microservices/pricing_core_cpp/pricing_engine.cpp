#include "pricing_engine.h"
#include <ctime>
#include <cmath>

namespace magadrive {

PricingEngine::PricingEngine() {
    // Инициализация множителей для классов
    class_multipliers_[VehicleClass::COMFORT] = 1.0;
    class_multipliers_[VehicleClass::BUSINESS] = 1.8;
    class_multipliers_[VehicleClass::XL] = 2.5;
    
    // Множители по расстоянию
    base_distance_multiplier_ = 1.0;
    long_distance_threshold_m_ = 10000.0; // 10 км
    long_distance_multiplier_ = 0.8; // Скидка на длинные поездки
    
    // Множители по времени суток
    peak_hour_multiplier_ = 1.3;  // Пиковые часы (7-9, 17-19)
    night_hour_multiplier_ = 1.2; // Ночные часы (22-6)
}

PricingResponse PricingEngine::calculatePrice(const PricingRequest& request) {
    PricingResponse response;
    
    // Получаем множители
    double distance_mult = getDistanceMultiplier(request.distance_m);
    double class_mult = getClassMultiplier(request.vehicle_class);
    double time_mult = getTimeOfDayMultiplier();
    
    // Рассчитываем финальную цену
    double final_price = request.base_price_rub * 
                        distance_mult * 
                        class_mult * 
                        request.surge_multiplier * 
                        time_mult;
    
    // Округляем до рублей
    response.final_price_rub = static_cast<int>(std::round(final_price));
    
    // Заполняем детали расчета
    response.distance_multiplier = distance_mult;
    response.class_multiplier = class_mult;
    response.surge_multiplier = request.surge_multiplier;
    response.time_multiplier = time_mult;
    response.currency = "RUB";
    
    return response;
}

double PricingEngine::getDistanceMultiplier(double distance_m) const {
    if (distance_m <= long_distance_threshold_m_) {
        // Стандартный множитель для коротких поездок
        return base_distance_multiplier_;
    } else {
        // Скидка для длинных поездок
        return long_distance_multiplier_;
    }
}

double PricingEngine::getClassMultiplier(VehicleClass vehicle_class) const {
    auto it = class_multipliers_.find(vehicle_class);
    if (it != class_multipliers_.end()) {
        return it->second;
    }
    return 1.0; // Fallback
}

double PricingEngine::getTimeOfDayMultiplier() const {
    time_t now = time(nullptr);
    struct tm* timeinfo = localtime(&now);
    int hour = timeinfo->tm_hour;
    
    // Пиковые часы: 7-9 и 17-19
    if ((hour >= 7 && hour <= 9) || (hour >= 17 && hour <= 19)) {
        return peak_hour_multiplier_;
    }
    
    // Ночные часы: 22-6
    if (hour >= 22 || hour <= 6) {
        return night_hour_multiplier_;
    }
    
    // Обычные часы
    return 1.0;
}

} // namespace magadrive
