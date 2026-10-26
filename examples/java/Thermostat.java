// Reads from standard input: echo -5 | java Thermostat
import java.util.Scanner;

public class Thermostat {
    public static void main(String[] args) {
        Scanner in = new Scanner(System.in);
        int temp = in.nextInt();

        if (temp < -10) {
            System.out.println("Freezing");
        } else if (temp <= 25) {
            System.out.println("Comfortable");
        } else {
            System.out.println("Hot");
        }
    }
}
