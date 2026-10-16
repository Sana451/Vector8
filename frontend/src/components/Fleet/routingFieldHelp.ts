export const ROUTING_FIELD_HELP = {
  height_in:
    "Total exterior height of the vehicle including cargo and roof equipment, in inches (1 in = 2.54 cm). Sent to HERE as vehicle[height] (in centimeters). The route avoids bridges, overpasses and tunnels with a posted clearance lower than this value. Interior cargo-box height does not count. Allowed 1-1968 (HERE limit of 50 m). If empty, height restrictions are ignored.",
  width_in:
    "Total exterior width of the vehicle, in inches. Sent to HERE as vehicle[width] (in centimeters). The route avoids narrow bridges, tunnels and roads closed to wide vehicles. Include side mirrors and protruding equipment; interior cargo-box width does not count. Allowed 1-1968. If empty, width restrictions are ignored.",
  length_in:
    "Total exterior length of the vehicle (including the trailer for a combination), in inches. Sent to HERE as vehicle[length] (in centimeters). The route avoids roads and turns where length is restricted by signs or state rules. Allowed 1-11811 (HERE limit of 300 m). If empty, length restrictions are ignored.",
  gross_weight_lbs:
    "Gross vehicle weight rating (GVWR): curb weight plus maximum load, in pounds. Sent to HERE as vehicle[grossWeight] (in kilograms). The route avoids bridges and roads with a gross weight limit below this value. Allowed 1-2,000,000. If empty, weight restrictions are ignored.",
  weight_per_axle_lbs:
    "Maximum load on a single axle, in pounds. Sent to HERE as vehicle[weightPerAxle] (in kilograms). The route avoids roads with an axle weight limit below this value. Must not exceed gross weight when it is set. Allowed 1-2,000,000. If empty, axle weight restrictions are ignored.",
  axle_count:
    "Total number of axles (tractor and trailers combined for a combination). Sent to HERE as vehicle[axleCount]. The route avoids roads where the number of axles is restricted. Allowed 2-255. If empty, axle count restrictions are ignored.",
  tires_count:
    "Total number of tires on the vehicle. Sent to HERE as vehicle[tiresCount]. Used for restrictions based on tire count (for example on some roads and bridges). Allowed 1-255. If empty, such restrictions are ignored.",
  trailer_count:
    "Number of trailers (0 means no trailer, e.g. a straight truck). Sent to HERE as vehicle[trailerCount]. The route avoids roads closed to combinations or limiting the number of trailers. Allowed 0-255. Trailer length and KPRA length can only be set when this is 1 or more.",
  trailer_length_in:
    "Trailer length, in inches. Sent to HERE as vehicle[trailerLength] (in centimeters). The route avoids roads with a trailer length limit. Allowed 1-787 (HERE limit of 20 m). Only when trailer count is 1 or more; must not exceed total length.",
  kpra_length_in:
    "Kingpin-to-rear-axle (KPRA) distance of the trailer, in inches. Sent to HERE as vehicle[kpraLength] (in centimeters). Applies to California and Idaho restrictions: the route avoids roads where KPRA exceeds the legal limit. Allowed 1-11811. Only when trailer count is 1 or more.",
  payload_capacity_lbs:
    "Payload capacity: maximum cargo weight, in pounds. Sent to HERE as vehicle[payloadCapacity] (in kilograms). The route avoids roads with a payload capacity restriction. Must not exceed gross weight when it is set. Allowed 1-2,000,000. If empty, such restrictions are ignored.",
  max_speed_mph:
    "Maximum speed of the vehicle, in miles per hour. Sent to HERE as vehicle[speedCap] (in m/s). It does not change which roads are allowed; it caps the speed used in the calculation so travel time is not more optimistic than at this speed. Allowed 1-156. If empty, posted road speed limits are used.",
} as const
