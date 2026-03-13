#include <Arduino.h>

// ===== Hardware configuration =====
#define ACCEL_PIN 1
#define TACH_PIN 4

// ===== Sampling configuration =====
const float SAMPLE_RATE = 3000.0;     // Hz
const int N = 512;                    // samples per run

// ===== Trial weight configuration =====
float trialWeightGrams = 10.0;        // user-added test weight
float trialAngleDeg = 0.0;            // where the trial weight was placed

// ===== Tachometer tracking =====
volatile uint32_t lastTach = 0;
volatile float rpm = 0;

// ===== Sample buffer =====
float samples[N];

// ===== Vector struct for vibration math =====
struct Vector {
    float x;
    float y;
};

Vector run1;
Vector run2;

// ===== Tach interrupt =====
void IRAM_ATTR tachISR()
{
    uint32_t now = micros();
    uint32_t period = now - lastTach;

    lastTach = now;

    if (period > 0)
        rpm = 60000000.0 / period;
}

// ===== Sample collection =====
void collectSamples()
{
    for (int i = 0; i < N; i++)
    {
        samples[i] = analogRead(ACCEL_PIN);
        delayMicroseconds(1000000 / SAMPLE_RATE);
    }
}

// ===== Goertzel frequency extraction =====
void computeGoertzel(float &amplitude, float &phase)
{
    float freq = rpm / 60.0;

    float k = 0.5 + ((N * freq) / SAMPLE_RATE);
    float w = (2.0 * PI / N) * k;

    float cosine = cos(w);
    float sine = sin(w);
    float coeff = 2 * cosine;

    float q0 = 0;
    float q1 = 0;
    float q2 = 0;

    for (int i = 0; i < N; i++)
    {
        q0 = coeff * q1 - q2 + samples[i];
        q2 = q1;
        q1 = q0;
    }

    float real = q1 - q2 * cosine;
    float imag = q2 * sine;

    amplitude = sqrt(real * real + imag * imag) / N;

    phase = atan2(imag, real) * 180 / PI;

    if (phase < 0)
        phase += 360;
}

// ===== Vector math =====
Vector polarToVector(float amp, float phaseDeg)
{
    float r = radians(phaseDeg);

    Vector v;
    v.x = amp * cos(r);
    v.y = amp * sin(r);

    return v;
}

Vector subtract(Vector a, Vector b)
{
    Vector r;
    r.x = a.x - b.x;
    r.y = a.y - b.y;
    return r;
}

float magnitude(Vector v)
{
    return sqrt(v.x * v.x + v.y * v.y);
}

float angleDeg(Vector v)
{
    float a = degrees(atan2(v.y, v.x));
    if (a < 0) a += 360;
    return a;
}

// ===== Balance solver =====
void computeBalance()
{
    Vector influence = subtract(run2, run1);

    float influenceMag = magnitude(influence);

    float vibrationPerGram = influenceMag / trialWeightGrams;

    float imbalanceMag = magnitude(run1);

    float neededWeight = imbalanceMag / vibrationPerGram;

    Vector correction;
    correction.x = -run1.x;
    correction.y = -run1.y;

    float angle = angleDeg(correction);

    Serial.println("------ BALANCE SOLUTION ------");

    Serial.print("Add weight: ");
    Serial.print(neededWeight);
    Serial.println(" grams");

    Serial.print("Angle: ");
    Serial.print(angle);
    Serial.println(" degrees");
}

// ===== Setup =====
void setup()
{
    Serial.begin(115200);

    pinMode(TACH_PIN, INPUT_PULLUP);
    attachInterrupt(TACH_PIN, tachISR, FALLING);

    analogReadResolution(12);

    Serial.println("Prop Balancer Ready");
    Serial.println("Run engine WITHOUT trial weight for Run 1");
}

// ===== Main loop =====
void loop()
{
    float amplitude;
    float phase;

    collectSamples();

    computeGoertzel(amplitude, phase);

    Serial.println("---- Measurement ----");

    Serial.print("RPM: ");
    Serial.println(rpm);

    Serial.print("Amplitude: ");
    Serial.println(amplitude);

    Serial.print("Phase: ");
    Serial.println(phase);

    static bool firstRunComplete = false;

    if (!firstRunComplete)
    {
        run1 = polarToVector(amplitude, phase);

        Serial.println("Run 1 stored.");
        Serial.println("Add trial weight and run again.");

        firstRunComplete = true;
    }
    else
    {
        run2 = polarToVector(amplitude, phase);

        Serial.println("Run 2 stored.");

        computeBalance();

        while (true)
        {
            delay(1000);
        }
    }

    delay(2000);
}